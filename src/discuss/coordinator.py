"""One-process assignment, health/exposure and report coordination."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Protocol

from .config import Config, Server
from .playback import Target
from .policy import ChannelPresence, choose_channel, fixed_assignments
from .reporting import Scheduler
from .service_logging import update_logging
from .speech import PipelineSink, SpeechPipeline
from .storage import Store

log = logging.getLogger(__name__)


class Listener(Protocol):
    name: str

    def ready(self, server: str) -> bool: ...
    def channels(self, server: str) -> list[ChannelPresence]: ...
    def current_channel(self, server: str) -> str | None: ...
    def connected(self, server: str) -> bool: ...
    def capture_ready(self, server: str) -> bool: ...
    def play_clip(self, server: str, target: Target, pcm: bytes, done: Callable[[], None]) -> bool: ...
    def stop_clip(self, server: str) -> None: ...
    async def assign(self, server: str, channel: str, sink: PipelineSink) -> None: ...
    async def release(self, server: str) -> None: ...
    async def notice(self, server: Server) -> None: ...
    async def publish(self, server: Server, page: str, period: str, index: int) -> str: ...
    async def publish_detections(self, server: Server, page: str) -> str: ...
    def speaker_name(self, server: str, member: str) -> str: ...
    async def close(self) -> None: ...
    async def reconfigure(self, config: Config) -> None: ...


class Coordinator:
    def __init__(
        self,
        config: Config,
        store: Store,
        pipeline: SpeechPipeline,
        listeners: Mapping[str, Listener],
        draw: Callable[[], float] = random.random,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config, self.store, self.pipeline = config, store, pipeline
        self.listeners = dict(listeners)
        self.draw = draw
        self.clock = clock or (lambda: datetime.now(UTC))
        self.scheduler = Scheduler(store)
        self._hunt_due: dict[str, float] = {}
        self._selected: dict[str, str | None] = {}
        self._notices: set[tuple[str, str, str]] = set()
        self._retry: dict[tuple[str, str], float] = {}
        self._report_retry: dict[str, float] = {}
        self.errors: dict[str, str] = {}
        self._loop_errors: dict[str, type[BaseException]] = {}
        self._lock = asyncio.Lock()
        self.pipeline.playback.start = lambda server, target, pcm, done: self.listeners[target.listener].play_clip(
            server, target, pcm, done
        )

        def stop_playback(server: str) -> None:
            for worker in self.listeners.values():
                worker.stop_clip(server)

        self.pipeline.playback.stop = stop_playback
        self.pipeline.detection_feed.bind(
            lambda server, page: self.listeners[server.primary_bot].publish_detections(server, page),
            lambda server, member: self.listeners[
                next(s.primary_bot for s in self.config.servers if s.server_id == server)
            ].speaker_name(server, member),
            lambda server: self.listeners[server.primary_bot].ready(server.server_id),
        )

    def _channels(self, worker: Listener, server: Server) -> list[ChannelPresence]:
        return [
            ChannelPresence(
                c.channel_id,
                tuple(m for m in c.members if not self.store.opted_out(server.server_id, m.member_id)),
                c.permitted,
                c.full,
            )
            for c in worker.channels(server.server_id)
        ]

    async def reload(self, config: Config, now: datetime) -> None:
        async with self._lock:
            log.info("configuration_reload_requested")
            expected = {b.name for b in config.bots if b.enabled}
            if expected != set(self.listeners):
                raise ValueError("Restart is required when enabled bot identities change")
            old_tokens = {b.name: b.token.get_secret_value() for b in self.config.bots if b.enabled}
            new_tokens = {b.name: b.token.get_secret_value() for b in config.bots if b.enabled}
            if old_tokens != new_tokens or config.transcription != self.config.transcription:
                raise ValueError("Restart is required when credentials or speech settings change")
            for server in self.config.servers:
                for worker in self.listeners.values():
                    self.store.monitor(worker.name, server.server_id, "0", [], now, healthy=False)
            await asyncio.gather(
                *(worker.release(s.server_id) for worker in self.listeners.values() for s in self.config.servers),
                return_exceptions=True,
            )
            for server in self.config.servers:
                self.pipeline.discard(server.server_id)
                self.pipeline.playback.discard(server.server_id, force=True)
            self.config = self.pipeline.config = config
            update_logging(config)
            self.pipeline.detection_feed.reconfigure(config)
            await asyncio.gather(*(worker.reconfigure(config) for worker in self.listeners.values()))
            self._hunt_due.clear()
            self._selected.clear()
            self._notices.clear()
            log.info("configuration_reloaded")

    async def tick(self, now: datetime, monotonic: float, *, include_reports: bool = True) -> None:
        async with self._lock:
            for segmenter in self.pipeline.segmenters:
                segmenter.expire(now)
            results = await asyncio.gather(
                *(self._server_tick(server, now, monotonic) for server in self.config.servers), return_exceptions=True
            )
            for server, result in zip(self.config.servers, results, strict=True):
                if isinstance(result, BaseException):
                    if self._loop_errors.get(server.server_id) is not type(result):
                        log.error(
                            "reconciliation_failed",
                            extra={"server": server.server_id},
                            exc_info=(type(result), result, result.__traceback__),
                        )
                    self._loop_errors[server.server_id] = type(result)
                    self.errors[server.server_id] = (
                        "Listener reconciliation failed; inspect local setup and permissions"
                    )
                elif self._loop_errors.pop(server.server_id, None) is not None:
                    log.info("reconciliation_loop_recovered", extra={"server": server.server_id})
            if include_reports:
                await self.report_tick(now, monotonic)

    async def report_tick(self, now: datetime, monotonic: float) -> None:
        self.pipeline.detection_feed.tick()
        for server in self.config.servers:
            targets = []
            if not self.store.disabled(server.server_id):
                for worker in self.listeners.values():
                    if not worker.capture_ready(server.server_id):
                        continue
                    channel = worker.current_channel(server.server_id)
                    for presence in self._channels(worker, server):
                        if presence.channel_id == channel:
                            targets.extend(
                                Target(worker.name, channel, m.member_id)
                                for m in presence.members
                                if not m.is_bot and m.can_transmit
                            )
            self.pipeline.playback.tick(server, now, targets)
        # Report/segmentation timers can run while a voice connection awaits its handshake.
        for segmenter in self.pipeline.segmenters:
            segmenter.expire(now)
        watermark = self.pipeline.watermark(now)
        for server in self.config.servers:
            self.scheduler.queue_due(server, watermark)
            self.scheduler.prune(server, watermark)
        await asyncio.gather(*(self._reports(server, monotonic) for server in self.config.servers))

    async def _server_tick(self, server: Server, now: datetime, monotonic: float) -> None:
        primary = self.listeners[server.primary_bot]
        targets: dict[str, str] = {}
        enabled = server.monitoring_enabled and not self.store.disabled(server.server_id)
        if enabled:
            if server.mode == "head_hunt" and primary.ready(server.server_id):
                channels = self._channels(primary, server)
                if monotonic >= self._hunt_due.get(server.server_id, 0):
                    self._selected[server.server_id] = choose_channel(server, channels, self.draw())
                    log.info(
                        "head_hunt_evaluated",
                        extra={
                            "server": server.server_id,
                            "channel": self._selected[server.server_id] or "idle",
                            "reason": "scheduled_evaluation",
                        },
                    )
                    self._hunt_due[server.server_id] = monotonic + server.head_hunt.interval_seconds
                chosen = self._selected.get(server.server_id)
                active = {
                    c.channel_id
                    for c in channels
                    if c.permitted
                    and not c.full
                    and any(
                        not m.is_bot and m.can_transmit and m.member_id not in server.privacy.excluded_member_ids
                        for m in c.members
                    )
                }
                if chosen in active:
                    targets[server.primary_bot] = chosen
            elif server.mode == "fixed_channels":
                for assignment in server.assignments:
                    worker = self.listeners[assignment.bot]
                    if worker.ready(server.server_id):
                        target = fixed_assignments(server, self._channels(worker, server)).get(assignment.bot)
                        if target is not None:
                            targets[assignment.bot] = target
        notice = (server.server_id, server.primary_bot, server.privacy.listening_notice)
        if targets and notice not in self._notices:
            try:
                key = ("notice", server.server_id)
                if monotonic < self._retry.get(key, 0):
                    targets.clear()
                    raise RuntimeError("Notice retry is waiting")
                await primary.notice(server)
                self._notices.add(notice)
            except Exception:
                if targets:
                    log.warning("notice_delivery_failed", extra={"server": server.server_id}, exc_info=True)
                    self._retry[("notice", server.server_id)] = monotonic + 10
                targets.clear()
                self.errors[server.server_id] = "Cannot publish the processing notice; check primary bot permissions"

        await asyncio.gather(
            *(
                self._reconcile(worker, server, targets.get(name), now, monotonic)
                for name, worker in self.listeners.items()
            )
        )
        if not enabled:
            self.pipeline.discard(server.server_id)

    async def _reconcile(
        self, worker: Listener, server: Server, target: str | None, now: datetime, monotonic: float
    ) -> None:
        key = (worker.name, server.server_id)
        current = worker.current_channel(server.server_id)
        try:
            if current is not None and current != target:
                log.info(
                    "assignment_released",
                    extra={
                        "server": server.server_id,
                        "identity": worker.name,
                        "previous_channel": current,
                        "channel": target or "idle",
                        "reason": "policy_target_changed" if target else "no_eligible_target",
                    },
                )
                if server.playback.mode == "first_curse":
                    self.pipeline.playback.unassign(server.server_id, worker.name)
                else:
                    self.pipeline.playback.discard(server.server_id)
                self.store.monitor(
                    worker.name,
                    server.server_id,
                    current,
                    [],
                    self.clock(),
                    healthy=worker.capture_ready(server.server_id) and self.pipeline.ready,
                )
                await worker.release(server.server_id)
                current = None
            if target is not None and (current != target or not worker.connected(server.server_id)):
                if monotonic >= self._retry.get(key, 0):
                    log.info(
                        "assignment_requested",
                        extra={
                            "server": server.server_id,
                            "identity": worker.name,
                            "channel": target,
                            "reason": "new_target" if current != target else "connection_recovery",
                        },
                    )
                    if current is not None:
                        await worker.release(server.server_id)
                    sink = self.pipeline.new_sink()
                    try:
                        await worker.assign(server.server_id, target, sink)
                        log.info(
                            "assignment_connected",
                            extra={"server": server.server_id, "identity": worker.name, "channel": target},
                        )
                    except Exception:
                        await sink.close("assignment failed")
                        raise
            channel = target or current
            occupants = next((c.members for c in self._channels(worker, server) if c.channel_id == channel), ())
            members = [m.member_id for m in occupants if not m.is_bot and m.can_transmit]
            healthy = target is not None and worker.capture_ready(server.server_id) and self.pipeline.ready
            self.store.monitor(
                worker.name,
                server.server_id,
                channel or "0",
                members,
                self.clock(),
                healthy=healthy,
                excluded=server.privacy.excluded_member_ids,
            )
        except Exception:
            log.warning(
                "assignment_retry_scheduled",
                extra={
                    "server": server.server_id,
                    "identity": worker.name,
                    "channel": target or current or "idle",
                    "delay_seconds": 10,
                },
                exc_info=True,
            )
            self._retry[key] = monotonic + 10
            self.errors[server.server_id] = "Listener unavailable; retrying this assignment"
            self.store.monitor(worker.name, server.server_id, current or target or "0", [], self.clock(), healthy=False)

    async def _reports(self, server: Server, monotonic: float) -> None:
        if monotonic < self._report_retry.get(server.server_id, 0):
            return
        primary = self.listeners[server.primary_bot]
        if not primary.ready(server.server_id):
            return
        try:
            await asyncio.wait_for(
                self.scheduler.deliver(
                    server.server_id, lambda page, period, index: primary.publish(server, page, period, index)
                ),
                30,
            )
        except Exception:
            log.warning("report_delivery_retry", extra={"server": server.server_id, "delay_seconds": 30}, exc_info=True)
            self._report_retry[server.server_id] = monotonic + 30
            self.errors[server.server_id] = "Report delivery pending; primary identity will retry"

    async def close(self, now: datetime) -> None:
        await self.pipeline.detection_feed.close()
        for server in self.config.servers:
            for worker in self.listeners.values():
                self.store.monitor(worker.name, server.server_id, "0", [], now, healthy=False)
        await asyncio.gather(*(w.close() for w in self.listeners.values()), return_exceptions=True)
        await self.pipeline.close()
