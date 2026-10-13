"""SDK boundary for authorized bot identities; all external text says server."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord_voice_reception import AudioFrame, VoiceRecvClient

from .calendar import window_at
from .config import Bot, Config, Server
from .coordinator import Coordinator
from .detection_reporting import notice
from .policy import ChannelPresence, MemberPresence
from .reporting import render, safe_word, standings
from .speech import PipelineSink, SpeechPipeline
from .storage import Store


def permitted_admin(interaction: discord.Interaction) -> bool:
    return interaction.guild_id is not None and interaction.permissions.administrator


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
        self._add_commands()
        self.tree.add_command(self.commands)

        @self.client.event
        async def on_ready() -> None:
            for server in self.config.servers:
                if server.primary_bot == self.name:
                    target = discord.Object(id=int(server.server_id))
                    self.tree.copy_global_to(guild=target)
                    with contextlib.suppress(discord.HTTPException):
                        await self.tree.sync(guild=target)

        @self.client.event
        async def on_voice_state_update(
            member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
        ) -> None:
            server_id = str(member.guild.id)
            policy = next((s for s in self.config.servers if s.server_id == server_id), None)
            if policy is None:
                return
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
        # SDK reconnect handles normal gateway faults. Bounded identity-level retries
        # handle faults escaping client.start without exposing exception contents.
        for attempt in range(5):
            if self._closing:
                return
            try:
                await self.client.start(self.bot.token.get_secret_value(), reconnect=True)
                return
            except discord.LoginFailure:
                self.setup_failed = True
                return
            except (OSError, discord.HTTPException):
                if attempt == 4:
                    return
                await asyncio.sleep(min(30, 2**attempt))

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
        if not isinstance(target, discord.VoiceChannel):
            raise ValueError("Configured voice channel is unavailable")
        if self._voice(server) is not None:
            await self.release(server)
        voice = await target.connect(cls=VoiceRecvClient, self_deaf=False, timeout=20)
        self._expected_channels[server] = channel
        try:
            voice.listen(MemberSink(self.client, sink, server, channel), decode_pcm=True)
        except Exception:
            await voice.disconnect(force=True)
            raise

    async def release(self, server: str) -> None:
        self._expected_channels.pop(server, None)
        voice = self._voice(server)
        if voice is not None:
            await voice.disconnect(force=True)

    def _report_channel(self, server: Server) -> discord.TextChannel:
        instance = self.client.get_guild(int(server.server_id))
        channel = instance.get_channel(int(server.report_channel_id)) if instance else None
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
        return person.display_name if person else "Member"

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
        message = await self._report_channel(server).send(page, allowed_mentions=discord.AllowedMentions.none())
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

    def _add_commands(self) -> None:
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
            await self._reply(
                interaction, render(window, standings(self.store, server.server_id, window, server.leaderboards))
            )

        @self.commands.command(name="words", description="Show a member's current-period tracked-word counts")
        @app_commands.choices(period=[app_commands.Choice(name=p, value=p) for p in ("day", "week", "month", "year")])
        async def words(
            interaction: discord.Interaction, member: discord.Member | None = None, period: str = "week"
        ) -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            if period not in {"day", "week", "month", "year"}:
                await self._reply(interaction, ["Unknown reporting period."])
                return
            window = window_at(datetime.now(UTC), server.leaderboards.timezone, period)
            target = str((member or interaction.user).id)
            counts = self.store.counts(server.server_id, window.start, window.end).get(target, {})
            rows = [f"{safe_word(word)}: {count}" for word, count in sorted(counts.items())]
            pages, current = [], f"Member {target} | current {period}"
            for row in rows:
                if len(current) + len(row) + 1 > 1900:
                    pages.append(current)
                    current = f"Member {target} | current {period}"
                current += "\n" + row
            pages.append(current if rows else current + "\nNo tracked detections.")
            await self._reply(interaction, pages)

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
                interaction, ["You are opted out. Existing statistics remain until deletion or retention."]
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

        @self.commands.command(name="delete_self", description="Delete your local statistics and opt out")
        async def delete_self(interaction: discord.Interaction) -> None:
            server = self._policy(interaction)
            if server is None:
                await self._reply(interaction, ["This command requires a configured Discord server."])
                return
            member = str(interaction.user.id)
            self.pipeline.discard(server.server_id, member)
            self.store.delete_member(server.server_id, member)
            self.store.set_opt_out(server.server_id, member, True, datetime.now(UTC))
            await self._reply(
                interaction,
                [
                    "Local statistics deleted; a minimal opt-out preference remains. "
                    "Already posted messages/backups require operator cleanup."
                ],
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
            rows = [f"Server {server.server_id}; speech admission ready={self.pipeline.ready}"]
            feed = self.pipeline.detection_feed
            rows.append(
                f"Detection feed: pending={sum(i.server == server.server_id for i in feed.pending)}, "
                f"service drops={feed.dropped}, expired={feed.expired}, delivery failures={feed.failures}"
            )
            if coordinator is not None:
                rows.extend(
                    f"Identity {name}: channel={worker.current_channel(server.server_id)}, "
                    f"connected={worker.connected(server.server_id)}, "
                    f"capture ready={worker.capture_ready(server.server_id)}"
                    for name, worker in coordinator.listeners.items()
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
