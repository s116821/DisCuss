"""SDK boundary for authorized bot identities; all external text says server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord_voice_reception import AudioFrame, VoiceRecvClient

from .calendar import window_at
from .config import Bot, Config, Server
from .coordinator import Coordinator
from .detection_reporting import notice, safe_text
from .playback import Target
from .policy import ChannelPresence, MemberPresence
from .quote_history import RESULT_LIMIT, SCAN_LIMIT, belongs, bounds, parse_line
from .reporting import render, render_word_counts, report_members, resolve_page_names, standings
from .speech import PipelineSink, SpeechPipeline
from .storage import Store

log = logging.getLogger(__name__)


def permitted_admin(interaction: discord.Interaction) -> bool:
    return interaction.guild_id is not None and interaction.permissions.administrator


class MemoryAudio(discord.AudioSource):
    """A single bounded PCM clip, erased after use; Discord reads 20 ms frames."""

    def __init__(self, pcm: bytes) -> None:
        self.pcm, self.offset = pcm, 0

    def read(self) -> bytes:
        frame = self.pcm[self.offset : self.offset + 3840]
        self.offset += len(frame)
        return frame.ljust(3840, b"\0") if frame else b""

    def cleanup(self) -> None:
        self.pcm = b""


class MemberSink:
    def __init__(self, client: discord.Client, sink: PipelineSink, server_id: str, channel_id: str) -> None:
        self.client, self.sink = client, sink
        self.server_id, self.channel_id = server_id, channel_id

    async def write(self, frame: AudioFrame) -> None:
        if str(frame.server_id) != self.server_id or str(frame.channel_id) != self.channel_id:
            return
        server = self.client.get_guild(frame.server_id)
        member = server.get_member(frame.member_id) if server else None
        if (
            member is not None
            and not member.bot
            and member.voice is not None
            and member.voice.channel is not None
            and member.voice.channel.id == frame.channel_id
        ):
            await self.sink.write(frame)

    async def close(self, reason: str) -> None:
        await self.sink.close(reason)


class DiscordListener:
    def __init__(self, bot: Bot, config: Config, store: Store, pipeline: SpeechPipeline) -> None:
        self.name, self.bot, self.config, self.store, self.pipeline = bot.name, bot, config, store, pipeline
        self.coordinator: Coordinator | None = None
        intents = discord.Intents.none()
        intents.guilds = intents.voice_states = True
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self.commands = app_commands.Group(
            name="discuss", description="Voice competition standings and privacy controls"
        )
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        self.setup_failed = False
        self._expected_channels: dict[str, str] = {}
        self._name_cache: dict[str, tuple[float, str]] = {}
        self._name_slots = asyncio.Semaphore(4)
        self._add_commands()
        self.tree.add_command(self.commands)

        @self.client.event
        async def on_ready() -> None:
            log.info("gateway_ready", extra={"identity": self.name})
            for server in self.config.servers:
                if server.primary_bot == self.name:
                    target = discord.Object(id=int(server.server_id))
                    self.tree.copy_global_to(guild=target)
                    with contextlib.suppress(discord.HTTPException):
                        await self.tree.sync(guild=target)

        @self.client.event
        async def on_disconnect() -> None:
            log.warning("gateway_disconnected", extra={"identity": self.name})

        @self.client.event
        async def on_resumed() -> None:
            log.info("gateway_resumed", extra={"identity": self.name})

        @self.client.event
        async def on_error(event_method: str, *args, **kwargs) -> None:
            log.error("gateway_callback_failed", extra={"identity": self.name, "reason": event_method}, exc_info=True)

        @self.client.event
        async def on_voice_state_update(
            member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
        ) -> None:
            server_id = str(member.guild.id)
            policy = next((s for s in self.config.servers if s.server_id == server_id), None)
            if policy is None:
                return
            if before.channel != after.channel:
                if self.client.user is not None and member.id == self.client.user.id:
                    log.info(
                        "bot_voice_state_changed",
                        extra={
                            "identity": self.name,
                            "server": member.guild.name,
                            "previous_channel": before.channel.name if before.channel else "disconnected",
                            "channel": after.channel.name if after.channel else "disconnected",
                        },
                    )
                    self.pipeline.playback.discard(server_id)
                else:
                    self.pipeline.playback.discard(server_id, str(member.id))
            channel_id = self.current_channel(server_id)
            occupants = next((c.members for c in self.channels(server_id) if c.channel_id == channel_id), ())
            healthy = (
                policy.monitoring_enabled
                and self.capture_ready(server_id)
                and self.pipeline.ready
                and not self.store.disabled(server_id)
            )
            if self.client.user is not None and member.id == self.client.user.id and after.channel is None:
                healthy = False
            self.store.monitor(
                self.name,
                server_id,
                channel_id or "0",
                [m.member_id for m in occupants if not m.is_bot and m.can_transmit],
                datetime.now(UTC),
                healthy=healthy,
                excluded=policy.privacy.excluded_member_ids,
            )

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"bot-identity:{self.name}")

    async def reconfigure(self, config: Config) -> None:
        old_primary = {s.server_id for s in self.config.servers if s.primary_bot == self.name}
        new_primary = {s.server_id for s in config.servers if s.primary_bot == self.name}
        self.config = config
        if self.client.is_ready():
            for server in old_primary - new_primary:
                target = discord.Object(id=int(server))
                self.tree.clear_commands(guild=target)
                with contextlib.suppress(discord.HTTPException):
                    await self.tree.sync(guild=target)
            for server in new_primary - old_primary:
                target = discord.Object(id=int(server))
                self.tree.copy_global_to(guild=target)
                with contextlib.suppress(discord.HTTPException):
                    await self.tree.sync(guild=target)

    async def _run(self) -> None:
        # The SDK reconnects an established gateway. Initial login can fail before
        # that loop exists, particularly while DNS/network trust initializes at boot.
        attempt, delay = 0, 1
        while not self._closing:
            attempt += 1
            try:
                log.info("gateway_connecting", extra={"identity": self.name, "attempt": attempt})
                async with self.client:
                    await self.client.start(self.bot.token.get_secret_value(), reconnect=True)
                return
            except (discord.LoginFailure, discord.PrivilegedIntentsRequired):
                log.error("gateway_authorization_failed", extra={"identity": self.name}, exc_info=True)
                self.setup_failed = True
                return
            except (
                OSError,
                aiohttp.ClientError,
                discord.HTTPException,
                discord.GatewayNotFound,
                discord.ConnectionClosed,
            ) as error:
                if self._closing:
                    return
                invalid_http = (
                    isinstance(error, discord.HTTPException) and 400 <= error.status < 500 and error.status != 429
                )
                invalid_gateway = isinstance(error, discord.ConnectionClosed) and error.code in {
                    4004,
                    4010,
                    4011,
                    4012,
                    4013,
                    4014,
                }
                if invalid_http or invalid_gateway:
                    log.error("gateway_setup_failed", extra={"identity": self.name}, exc_info=True)
                    self.setup_failed = True
                    return
                # The context closes sockets/sessions; clear reopens SDK state.
                # Its next context entry also initializes the client's asyncio loop.
                self.client.clear()
                log.warning(
                    "gateway_connection_failed",
                    extra={"identity": self.name, "attempt": attempt, "delay_seconds": delay},
                    exc_info=True,
                )
                await asyncio.sleep(delay)
                delay = min(30, delay * 2)

    def ready(self, server: str) -> bool:
        return self.client.is_ready() and self.client.get_guild(int(server)) is not None

    def _voice(self, server: str) -> VoiceRecvClient | None:
        instance = self.client.get_guild(int(server))
        voice = instance.voice_client if instance else None
        return voice if isinstance(voice, VoiceRecvClient) else None

    def current_channel(self, server: str) -> str | None:
        voice = self._voice(server)
        return str(voice.channel.id) if voice else None

    def connected(self, server: str) -> bool:
        voice = self._voice(server)
        return (
            voice is not None
            and voice.is_connected()
            and self.ready(server)
            and str(voice.channel.id) == self._expected_channels.get(server)
        )

    def capture_ready(self, server: str) -> bool:
        voice = self._voice(server)
        return (
            self.connected(server)
            and voice is not None
            and voice.receiver_health is not None
            and voice.receiver_health.capture_ready
        )

    def channels(self, server: str) -> list[ChannelPresence]:
        instance = self.client.get_guild(int(server))
        if instance is None or instance.me is None or not self.client.is_ready():
            return []
        current = self.current_channel(server)
        result = []
        for channel in instance.voice_channels:
            permissions = channel.permissions_for(instance.me)
            occupants = tuple(
                MemberPresence(str(m.id), m.bot, m.voice is not None and not m.voice.mute and not m.voice.suppress)
                for m in channel.members
            )
            full = bool(
                channel.user_limit and len(channel.members) >= channel.user_limit and str(channel.id) != current
            )
            result.append(
                ChannelPresence(str(channel.id), occupants, permissions.view_channel and permissions.connect, full)
            )
        return result

    async def assign(self, server: str, channel: str, sink: PipelineSink) -> None:
        instance = self.client.get_guild(int(server))
        target = instance.get_channel(int(channel)) if instance else None
        if instance is None or not isinstance(target, discord.VoiceChannel):
            raise ValueError("Configured voice channel is unavailable")
        if self._voice(server) is not None:
            await self.release(server)
        log.info("voice_join_requested", extra={"identity": self.name, "server": instance.name, "channel": target.name})
        voice = await target.connect(cls=VoiceRecvClient, self_deaf=False, timeout=20)
        self._expected_channels[server] = channel
        try:
            voice.listen(MemberSink(self.client, sink, server, channel), decode_pcm=True)
            log.info(
                "voice_capture_ready", extra={"identity": self.name, "server": instance.name, "channel": target.name}
            )
        except Exception:
            log.error("voice_capture_failed", extra={"identity": self.name, "server": server}, exc_info=True)
            await voice.disconnect(force=True)
            raise

    async def release(self, server: str) -> None:
        self.pipeline.playback.discard(server)
        self._expected_channels.pop(server, None)
        voice = self._voice(server)
        if voice is not None:
            log.info(
                "voice_leave_requested", extra={"identity": self.name, "server": server, "channel": voice.channel.name}
            )
            await voice.disconnect(force=True)

    def play_clip(self, server: str, target: Target, pcm: bytes, done: Callable[[], None]) -> bool:
        voice = self._voice(server)
        if (
            voice is None
            or not self.capture_ready(server)
            or self.current_channel(server) != target.channel
            or voice.is_playing()
            or voice.is_paused()
        ):
            return False
        instance = self.client.get_guild(int(server))
        if instance is None or instance.me is None or not voice.channel.permissions_for(instance.me).speak:
            return False
        loop = asyncio.get_running_loop()
        source = MemoryAudio(pcm)
        try:

            def finished(error: Exception | None) -> None:
                if error:
                    log.warning(
                        "playback_transport_failed",
                        extra={"identity": self.name, "server": server, "error_type": type(error).__name__},
                    )
                loop.call_soon_threadsafe(done)

            voice.play(source, after=finished)
        except Exception:
            source.cleanup()
            raise
        return True

    def stop_clip(self, server: str) -> None:
        voice = self._voice(server)
        if voice is not None:
            source = voice.source
            voice.stop()
            if isinstance(source, MemoryAudio):
                source.cleanup()

    def _report_channel(self, server: Server, channel_id: str | None = None) -> discord.TextChannel:
        instance = self.client.get_guild(int(server.server_id))
        channel = instance.get_channel(int(channel_id or server.report_channel_id)) if instance else None
        if not isinstance(channel, discord.TextChannel) or instance is None or instance.me is None:
            raise ValueError("Configured report channel is unavailable")
        permissions = channel.permissions_for(instance.me)
        if not permissions.view_channel or not permissions.send_messages:
            raise ValueError("Primary bot lacks report channel permissions")
        return channel

    async def notice(self, server: Server) -> None:
        report_channel = self._report_channel(server)
        instance = self.client.get_guild(int(server.server_id))
        destination_id = server.detection_reporting.channel_id or server.report_channel_id
        destination = instance.get_channel(int(destination_id)) if instance else None
        name = destination.name if isinstance(destination, discord.TextChannel) else None
        await report_channel.send(
            notice(server, name), allowed_mentions=discord.AllowedMentions.none(), suppress_embeds=True
        )

    def speaker_name(self, server: str, member: str) -> str:
        instance = self.client.get_guild(int(server))
        person = instance.get_member(int(member)) if instance else None
        person = person or self.client.get_user(int(member))
        if person is not None and isinstance(person.display_name, str):
            return person.display_name
        cached = self._name_cache.get(member)
        return cached[1] if cached and cached[0] > time.monotonic() else "Unknown member"

    async def resolve_members(self, server: str, members: Iterable[str]) -> None:
        async def resolve(member: str) -> None:
            if self.speaker_name(server, member) != "Unknown member":
                return
            cached = self._name_cache.get(member)
            if cached and cached[0] > time.monotonic():
                return
            async with self._name_slots:
                try:
                    person = await asyncio.wait_for(self.client.fetch_user(int(member)), 5)
                    name, expiry = person.display_name, 900
                except (discord.HTTPException, OSError, TimeoutError):
                    name, expiry = "Unknown member", 60
                if len(self._name_cache) >= 4096:
                    self._name_cache.pop(next(iter(self._name_cache)))
                self._name_cache[member] = time.monotonic() + expiry, name

        await asyncio.gather(*(resolve(member) for member in set(members)))

    def channel_name(self, server: str, channel: str | None) -> str:
        if channel is None:
            return "Not connected"
        instance = self.client.get_guild(int(server))
        target = instance.get_channel(int(channel)) if instance else None
        return "#" + safe_text(target.name, 64) if target is not None else "Unavailable channel"

    async def publish_detections(self, server: Server, page: str) -> str:
        channel_id = server.detection_reporting.channel_id or server.report_channel_id
        instance = self.client.get_guild(int(server.server_id))
        channel = instance.get_channel(int(channel_id)) if instance else None
        if not isinstance(channel, discord.TextChannel) or instance is None or instance.me is None:
            raise ValueError("Configured detection channel is unavailable")
        permissions = channel.permissions_for(instance.me)
        if not permissions.view_channel or not permissions.send_messages:
            raise ValueError("Primary bot lacks detection channel permissions")
        message = await channel.send(page, allowed_mentions=discord.AllowedMentions.none(), suppress_embeds=True)
        return str(message.id)

    async def publish(self, server: Server, page: str, period: str, index: int) -> str:
        await self.resolve_members(server.server_id, report_members(page))
        page = resolve_page_names(page, lambda member: self.speaker_name(server.server_id, member))
        message = await self._report_channel(server, server.leaderboards.report_channel_id).send(
            page, allowed_mentions=discord.AllowedMentions.none(), suppress_embeds=True
        )
        return str(message.id)

    def _policy(self, interaction: discord.Interaction) -> Server | None:
        return next(
            (s for s in self.config.servers if str(interaction.guild_id) == s.server_id and s.primary_bot == self.name),
            None,
        )

    async def _reply(self, interaction: discord.Interaction, pages: list[str]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        for page in pages:
            await interaction.followup.send(page, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def quote_pages(
        self,
        interaction: discord.Interaction,
        server: Server,
        member: discord.Member,
        since: str | None,
        until: str | None,
    ) -> list[str]:
        start, end = bounds(since, until, server.leaderboards.timezone, datetime.now(UTC))
        channel = self._report_channel(server, server.detection_reporting.channel_id)
        guild = interaction.guild
        requester = (
            interaction.user
            if isinstance(interaction.user, discord.Member)
            else (guild.get_member(interaction.user.id) if guild else None)
        )
        if requester is None or guild is None or guild.me is None:
            return ["Quote history requires current server membership."]
        for person in (requester, guild.me):
            permissions = channel.permissions_for(person)
            if not permissions.view_channel or not permissions.read_message_history:
                return ["You and the bot need View Channel and Read Message History in the detection channel."]
        if self.client.user is None:
            return ["The primary bot is not ready."]
        rows, scanned, limited = [], 0, False
        # Messages can be posted after recognition/batching. Match the timestamp
        # inside the report, while bounding both the API scan and delayed window.
        async for message in channel.history(
            limit=SCAN_LIMIT,
            after=start - timedelta(seconds=1),
            before=end + timedelta(hours=1),
            oldest_first=False,
        ):
            scanned += 1
            if message.author.id != self.client.user.id:
                continue
            for line in message.content.splitlines():
                parsed = parse_line(line, server.leaderboards.timezone)
                if parsed is None:
                    continue
                quote, speaker, at = parsed
                if start <= at < end and belongs(
                    speaker, at, str(member.id), member.display_name, self.store, server.server_id
                ):
                    rows.append(
                        f"“{quote}” — {safe_text(member.display_name, 64)}, "
                        f"{at.astimezone(ZoneInfo(server.leaderboards.timezone)):%b %d, %Y @ %I:%M %p %Z} "
                        f"· [original report]({message.jump_url})"
                    )
                    if len(rows) >= RESULT_LIMIT:
                        limited = True
                        break
            if limited:
                break
        heading = f"**Published quotes — {safe_text(member.display_name, 64)}**"
        if not rows:
            rows = ["No attributable reports found in this range. Deleted or unavailable history cannot be recovered."]
        pages, page = [], heading
        for row in rows:
            if len(page.encode("utf-16-le")) // 2 + len(row.encode("utf-16-le")) // 2 + 1 > 1800:
                pages.append(page)
                page = heading
            page += "\n" + row
        pages.append(page)
        if limited or scanned >= SCAN_LIMIT:
            pages.append("Search limit reached (20 results / 2,000 messages). Narrow the time range for more.")
        return pages

    def _add_commands(self) -> None:
        @self.commands.command(name="quotes", description="Find a member's published quotes in a time range")
        @app_commands.describe(
            since="Start date/time or HH:MM today; leading zeros; ±HH:MM = UTC offset; server timezone default",
            until="Exclusive end date/time or HH:MM today; leading zeros; ±HH:MM = UTC offset; default now",
        )
        async def quotes(
            interaction: discord.Interaction,
            member: discord.Member,
            since: str | None = None,
            until: str | None = None,
        ) -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            try:
                pages = await self.quote_pages(interaction, server, member, since, until)
            except ValueError as error:
                pages = [str(error)]
            except (discord.HTTPException, OSError):
                pages = ["Discord report history is unavailable; check channel permissions and try again."]
            await self._reply(interaction, pages)

        @self.commands.command(name="standings", description="Show total and scaled current-period standings")
        @app_commands.choices(period=[app_commands.Choice(name=p, value=p) for p in ("day", "week", "month", "year")])
        async def current(interaction: discord.Interaction, period: str = "week") -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            if period not in {"day", "week", "month", "year"}:
                await self._reply(interaction, ["Unknown reporting period."])
                return
            window = window_at(datetime.now(UTC), server.leaderboards.timezone, period)
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            board = standings(self.store, server.server_id, window, server.leaderboards)
            await self.resolve_members(server.server_id, {r.member_id for r in board.total + board.scaled})
            await self._reply(
                interaction,
                render(
                    window,
                    board,
                    member_name=lambda member: self.speaker_name(server.server_id, member),
                    timezone=server.leaderboards.timezone,
                    show_scaled=server.leaderboards.scaled.enabled,
                ),
            )

        @self.commands.command(name="words", description="Show a member's current-period tracked-word counts")
        @app_commands.choices(period=[app_commands.Choice(name=p, value=p) for p in ("day", "week", "month", "year")])
        async def words(interaction: discord.Interaction, member: discord.Member, period: str = "week") -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            if period not in {"day", "week", "month", "year"}:
                await self._reply(interaction, ["Unknown reporting period."])
                return
            window = window_at(datetime.now(UTC), server.leaderboards.timezone, period)
            target = str(member.id)
            counts = self.store.counts(server.server_id, window.start, window.end).get(target, {})
            await self._reply(
                interaction, render_word_counts(window, counts, member.display_name, server.leaderboards.timezone)
            )

        @self.commands.command(name="opt_out", description="Stop collecting your future voice statistics")
        async def opt_out(interaction: discord.Interaction) -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            member = str(interaction.user.id)
            self.store.set_opt_out(server.server_id, member, True, datetime.now(UTC))
            self.pipeline.discard(server.server_id, member)
            await self._reply(
                interaction,
                ["You are opted out. Collected results and posted reports remain; opt_in resumes participation."],
            )

        @self.commands.command(name="opt_in", description="Resume future collection if server policy permits")
        async def opt_in(interaction: discord.Interaction) -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            self.store.set_opt_out(server.server_id, str(interaction.user.id), False, datetime.now(UTC))
            await self._reply(
                interaction, ["Opt-out preference cleared. Server exclusions and monitoring policy still apply."]
            )

        @self.commands.command(name="monitoring", description="Administrator: enable or disable server monitoring")
        async def monitoring(interaction: discord.Interaction, enabled: bool) -> None:
            server = self._policy(interaction)
            if server is None or not permitted_admin(interaction):
                await self._reply(interaction, ["Server administrator permission is required."])
                return
            self.store.set_disabled(server.server_id, not enabled)
            if not enabled:
                self.pipeline.discard(server.server_id)
            await self._reply(interaction, ["Monitoring preference saved; configuration/privacy policy still applies."])

        @self.commands.command(name="status", description="Administrator: view local listener and pipeline readiness")
        async def status(interaction: discord.Interaction) -> None:
            server = self._policy(interaction)
            if server is None or not permitted_admin(interaction):
                await self._reply(interaction, ["Server administrator permission is required."])
                return
            coordinator = self.coordinator
            instance = self.client.get_guild(int(server.server_id))
            title = safe_text(instance.name, 64) if instance else "Server"
            rows = [f"**{title} — service status**", f"Speech processing ready: {self.pipeline.ready}"]
            rows.append(
                f"Speech queue: {len(self.pipeline.queue)} chunks; "
                f"oldest capture {self.pipeline.oldest_capture_age_seconds:.1f}s; "
                f"last recognition {self.pipeline.last_inference_seconds:.1f}s; "
                f"drops {self.pipeline.dropped}; failures {self.pipeline.failures}"
            )
            rows.append(
                f"Replay: {'enabled' if server.playback.enabled else 'disabled'}, {server.playback.interval_seconds}s "
                f"{server.playback.mode}; played {self.pipeline.playback.played}, "
                f"failed {self.pipeline.playback.failures}"
            )
            feed = self.pipeline.detection_feed
            rows.append(
                f"Detection feed: pending={sum(i.server == server.server_id for i in feed.pending)}, "
                f"service drops={feed.dropped}, expired={feed.expired}, delivery failures={feed.failures}"
            )
            if coordinator is not None:
                for name, worker in coordinator.listeners.items():
                    user = getattr(getattr(worker, "client", None), "user", None)
                    label = safe_text(user.display_name if user else name, 64)
                    channel = self.channel_name(server.server_id, worker.current_channel(server.server_id))
                    rows.append(
                        f"Listener {label}: {channel}, connected={worker.connected(server.server_id)}, "
                        f"capture ready={worker.capture_ready(server.server_id)}"
                    )
                if server.server_id in coordinator.errors:
                    rows.append(coordinator.errors[server.server_id])
            await self._reply(interaction, ["\n".join(rows)])

    async def close(self) -> None:
        self._closing = True
        await self.client.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
