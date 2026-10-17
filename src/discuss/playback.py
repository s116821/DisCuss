"""Weighted, bounded in-memory replay cycles; no recording files or transcript storage."""

from __future__ import annotations

import contextlib
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from .config import Server
from .policy import weights

if TYPE_CHECKING:
    from .lexicon import Match
    from .speech import SpeechChunk, SpeechWord

PCM_BYTES_PER_SECOND = 192000


@dataclass(frozen=True, slots=True)
class Target:
    listener: str
    channel: str
    member: str


@dataclass(slots=True)
class Cycle:
    start: datetime
    end: datetime
    listen_at: datetime
    target: Target | None
    clip: bytes | None = field(default=None, repr=False)
    play_at: datetime | None = None
    consumed: bool = False
    captured: bool = False


class PlaybackController:
    def __init__(self, allowed: Callable[[str, str], bool], draw: Callable[[], float] = random.random) -> None:
        self.allowed, self.draw = allowed, draw
        self.cycles: dict[str, Cycle] = {}
        self.active: dict[str, Target] = {}
        self.clock: Callable[[], datetime] = lambda: datetime.now(UTC)
        self.start: Callable[[str, Target, bytes, Callable[[], None]], bool] = lambda s, t, p, done: False
        self.stop: Callable[[str], None] = lambda s: None
        self.played = self.skipped = self.failures = 0

    def discard(self, server: str, member: str | None = None, *, force: bool = False) -> None:
        cycle = self.cycles.get(server)
        if not force and ((cycle is not None and cycle.captured) or server in self.active):
            return
        if cycle and (member is None or cycle.target is not None and cycle.target.member == member):
            cycle.clip, cycle.target, cycle.consumed = None, None, True
        active = self.active.get(server)
        if active and (member is None or active.member == member):
            with contextlib.suppress(Exception):
                self.stop(server)
            self.active.pop(server, None)
        if member is None:
            self.cycles.pop(server, None)

    def _select(self, policy: Server, targets: Sequence[Target]) -> Target | None:
        priority = weights(policy.head_hunt)
        weighted = [(t, priority.get(t.member, policy.head_hunt.default_weight)) for t in targets]
        total = sum(w for _, w in weighted)
        if total <= 0:
            return None
        choice = self.draw() * total
        for target, weight in weighted:
            choice -= weight
            if choice < 0:
                return target
        return None

    def tick(self, policy: Server, now: datetime, targets: Sequence[Target]) -> None:
        key, settings = policy.server_id, policy.playback
        enabled = settings.enabled and policy.monitoring_enabled
        if not enabled:
            self.discard(key)
            if key not in self.cycles:
                return
        targets = tuple({t.member: t for t in targets if enabled and self.allowed(key, t.member)}.values())
        active = self.active.get(key)
        if active is not None and active not in targets:
            self.discard(key, active.member)
        cycle = self.cycles.get(key)
        if cycle is None and not targets:
            return
        if cycle is not None and cycle.target is not None and cycle.target not in targets:
            self.discard(key, cycle.target.member)
        if cycle is not None and cycle.clip is not None and cycle.play_at is not None and now >= cycle.play_at:
            # Cadence starts on the boundary; allow one scheduler tick of jitter, never stale catch-up.
            deadline = cycle.end + timedelta(seconds=2 if settings.mode == "cadence" else 0)
            clip, target = cycle.clip, cycle.target
            cycle.clip, cycle.consumed = None, True
            if target is not None and now <= deadline and key not in self.active:
                self.active[key] = target

                def done(server: str = key, expected: Target = target) -> None:
                    if self.active.get(server) is expected:
                        self.active.pop(server, None)

                try:
                    started = self.start(key, target, clip, done)
                except Exception:
                    started = False
                if started:
                    self.played += 1
                else:
                    done()
                    self.failures += 1
            else:
                self.skipped += 1
        if cycle is None or now >= cycle.end:
            if cycle is not None and not cycle.consumed:
                self.skipped += 1
            if not targets:
                self.cycles.pop(key, None)
                return
            start = now if cycle is None else cycle.end
            interval = timedelta(seconds=settings.interval_seconds)
            if now >= start + interval:
                start += interval * int((now - start) // interval)
            target = self._select(policy, targets)
            delay = self.draw() * max(0, settings.interval_seconds - settings.max_clip_seconds - 1)
            listen_at = start + timedelta(seconds=delay if settings.mode == "random" else 0)
            self.cycles[key] = Cycle(start, start + interval, listen_at, target)

    def offer(self, policy: Server, chunk: SpeechChunk, words: Sequence[SpeechWord], matches: Sequence[Match]) -> None:
        from .lexicon import tokens

        key, now = policy.server_id, self.clock()
        cycle = self.cycles.get(key)
        if (
            not policy.playback.enabled
            or cycle is None
            or cycle.target is None
            or cycle.consumed
            or cycle.clip is not None
            or key in self.active
            or now >= cycle.end
            or (cycle.target.member, cycle.target.channel) != (chunk.member_id, chunk.channel_id)
            or not self.allowed(key, chunk.member_id)
        ):
            return
        token_words = [word for word in words for _ in tokens(word.text)]
        duration = len(chunk.pcm) / PCM_BYTES_PER_SECOND
        for match in matches:
            if match.token_start >= len(token_words) or match.token_end > len(token_words):
                continue
            first, last = token_words[match.token_start], token_words[match.token_end - 1]
            detected_at = chunk.started_at + timedelta(seconds=first.start_seconds)
            if not cycle.listen_at <= detected_at < cycle.end:
                continue
            lower = max(
                0.0,
                first.start_seconds - policy.playback.context_seconds,
                (cycle.listen_at - chunk.started_at).total_seconds(),
            )
            upper = min(
                duration,
                (last.end_seconds or last.start_seconds + 0.5) + policy.playback.context_seconds,
                lower + policy.playback.max_clip_seconds,
                (cycle.end - chunk.started_at).total_seconds(),
            )
            start, end = int(lower * 48000) * 4, int(upper * 48000) * 4
            if end <= start:
                continue
            cycle.clip = chunk.pcm[start:end]
            cycle.captured = True
            if policy.playback.mode == "cadence":
                cycle.play_at = cycle.end
            else:
                remaining = max(0.0, (cycle.end - now).total_seconds() - len(cycle.clip) / PCM_BYTES_PER_SECOND)
                cycle.play_at = now + timedelta(seconds=self.draw() * remaining)
            return
