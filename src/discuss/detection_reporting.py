"""Bounded, opt-in, memory-only recognized-context publication."""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
import unicodedata
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from .config import Config, Privacy, Server
from .lexicon import TOKEN, Match
from .storage import Store

MAX_INSTANCES = 4096
MAX_BYTES = 4194304
MAX_TEXT = 16000
MAX_EXCERPT_UNITS = 750
PAGE_UNITS = 1900
HEADER = ""
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def safe_text(text: str, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", "".join(c for c in text if unicodedata.category(c) not in {"Cc", "Cf"} or c.isspace()))
    if limit is not None:
        text = text.strip()
        result, size = [], 0
        for char in text:
            size += units(char)
            if size > limit:
                result.append("…")
                break
            result.append(char)
        text = "".join(result)
    text = text.replace("@", "＠").replace("\\", "\\\\")
    return re.sub(r"([`*_~|>\[\]()])", r"\\\1", text)


def original_spans(text: str) -> list[tuple[int, int]]:
    """Align the lexicon's normalized tokens with recognized original characters."""
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    pieces = [unicodedata.normalize("NFKC", char).casefold().replace("’", "'") for char in text]
    if "".join(pieces) == normalized:
        starts = [i for i, piece in enumerate(pieces) for _ in piece]
        ends = [i + 1 for i, piece in enumerate(pieces) for _ in piece]
    else:  # composed combining characters require alignment across characters
        starts, ends = [0] * len(normalized), [0] * len(normalized)
        for _, a, b, c, d in SequenceMatcher(None, text, normalized, autojunk=False).get_opcodes():
            if c == d:
                continue
            for index in range(c, d):
                starts[index] = a + (index - c) * (b - a) // (d - c)
                ends[index] = a + ((index - c + 1) * (b - a) + d - c - 1) // (d - c)
    return [(starts[m.start()], ends[m.end() - 1]) for m in TOKEN.finditer(normalized)]


@dataclass(frozen=True, slots=True)
class Instance:
    server: str
    channel: str
    member: str
    chunk: str
    ordinal: int
    at: datetime
    quote: str = field(repr=False)
    count: int
    queued_at: float
    serial: int = 0

    @property
    def size(self) -> int:
        return len(self.quote.encode("utf-8")) + 128


def instances(
    server: str,
    channel: str,
    member: str,
    chunk: str,
    text: str,
    matches: list[Match],
    times: list[datetime],
    context: int,
    queued_at: float,
) -> list[Instance]:
    if len(text) > MAX_TEXT or len(matches) != len(times):
        raise ValueError("Context input exceeds bounds or has inconsistent timing")
    spans = original_spans(text)

    def bounds(start: int, end: int) -> tuple[int, int]:
        return spans[start][0] if start else 0, spans[end][0] if end < len(spans) else len(text)

    def fits(start: int, end: int, count: int) -> bool:
        a, b = bounds(start, end)
        return units(text[a:b]) <= MAX_EXCERPT_UNITS and units(safe_text(text[a:b])) + 4 * count <= 1500

    groups: list[tuple[int, int, list[int]]] = []
    for index, match in enumerate(matches):
        start, end = max(0, match.token_start - context), min(len(spans), match.token_end + context)
        if end <= start or match.token_end > len(spans):
            raise ValueError("Context token coordinates are invalid")
        if groups and start < groups[-1][1] and fits(groups[-1][0], end, len(groups[-1][2]) + 1):
            previous = groups[-1]
            groups[-1] = previous[0], max(previous[1], end), [*previous[2], index]
        else:
            groups.append((start, end, [index]))
    result = []
    for start, end, indexes in groups:
        left, right = bounds(start, end)
        if not fits(start, end, len(indexes)):
            # Discard pathological oversized windows, never alter persisted counts.
            continue
        cursor, pieces = left, []
        highlights: list[tuple[int, int]] = []
        for index in indexes:
            match = matches[index]
            a, b = spans[match.token_start][0], spans[match.token_end - 1][1]
            if highlights and a <= highlights[-1][1]:
                highlights[-1] = highlights[-1][0], max(highlights[-1][1], b)
            else:
                highlights.append((a, b))
        for a, b in highlights:
            pieces.extend((safe_text(text[cursor:a]), "**" + safe_text(text[a:b]) + "**"))
            cursor = max(cursor, b)
        pieces.append(safe_text(text[cursor:right]))
        quote = "".join(pieces).strip()
        result.append(
            Instance(
                server,
                channel,
                member,
                chunk,
                indexes[0],
                min(times[i] for i in indexes),
                quote,
                len(indexes),
                queued_at,
            )
        )
    return result


def render(instance: Instance, speaker: str, server: Server) -> str:
    at = instance.at.astimezone(ZoneInfo(server.leaderboards.timezone))
    stamp = f"{MONTHS[at.month - 1]} {at.day}, {at.year} @ {at.hour % 12 or 12}:{at.minute:02d} "
    stamp += f"{'am' if at.hour < 12 else 'pm'} {at.tzname()}"
    return f"“{instance.quote}” — {safe_text(speaker, 64)}, {stamp}"


def notice(server: Server, channel_name: str | None = None) -> str:
    settings = server.detection_reporting
    destination = f"#{safe_text(channel_name)}" if channel_name else "the configured reporting channel"
    disclosure = f"excerpts go to {destination}"
    text = server.privacy.listening_notice
    if server.playback.enabled:
        text = text.replace("audio/transcripts are discarded;", "captured clips may replay after opt-out;")
        if "captured clips" not in text:
            text += " Captured clips may replay after opt-out."
    if not settings.enabled:
        return text
    if server.privacy.listening_notice == Privacy.model_fields["listening_notice"].default:
        return text.replace("locally;", f"locally; {disclosure};", 1)
    return text + f" {disclosure[0].upper() + disclosure[1:]}."


class DetectionFeed:
    def __init__(self, config: Config, store: Store, allowed: Callable[[str, str], bool]) -> None:
        self.config, self.store, self.allowed = config, store, allowed
        self.servers = {s.server_id: s for s in config.servers}
        self.pending: deque[Instance] = deque()
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.inflight: dict[str, asyncio.Task[str]] = {}
        self.inflight_items: dict[str, list[Instance]] = {}
        self.due: dict[str, float] = {}
        self.batches: dict[str, set[int]] = {}
        self._serial = 0
        self.clock: Callable[[], datetime] = lambda: datetime.now(UTC)
        self.monotonic: Callable[[], float] = time.monotonic
        self._send: Callable[[Server, str], Awaitable[str]] | None = None
        self._name: Callable[[str, str], str] = lambda server, member: "Member"
        self._ready: Callable[[Server], bool] = lambda server: False
        self.dropped = self.expired = self.sent_pages = self.failures = 0
        self._closed = False

    def bind(
        self,
        send: Callable[[Server, str], Awaitable[str]],
        name: Callable[[str, str], str],
        ready: Callable[[Server], bool],
    ) -> None:
        self._send, self._name, self._ready = send, name, ready

    @property
    def pending_bytes(self) -> int:
        return sum(item.size for item in self.pending)

    def policy(self, server: str) -> Server | None:
        return self.servers.get(server)

    def permitted(self, item: Instance) -> bool:
        server = self.policy(item.server)
        return bool(
            server
            and server.detection_reporting.enabled
            and server.privacy.context_reporting_acknowledged
            and self.allowed(item.server, item.member)
            and self.store.db.execute(
                "SELECT 1 FROM chunks WHERE server=? AND member=? AND chunk=?", (item.server, item.member, item.chunk)
            ).fetchone()
        )

    def discard(self, server: str, member: str | None = None) -> None:
        self.pending = deque(
            i for i in self.pending if not (i.server == server and (member is None or i.member == member))
        )
        if any(member is None or i.member == member for i in self.inflight_items.get(server, [])):
            task = self.inflight.get(server)
            if task:
                task.cancel()
        if not any(i.server == server for i in self.pending):
            self.due.pop(server, None)

    def reconfigure(self, config: Config) -> None:
        for server in self.config.servers:
            self.discard(server.server_id)
        self.pending.clear()
        self.due.clear()
        self.batches.clear()
        self.config = config
        self.servers = {s.server_id: s for s in config.servers}

    def offer(
        self,
        server: str,
        channel: str,
        member: str,
        chunk: str,
        text: str,
        matches: list[Match],
        times: list[datetime],
    ) -> None:
        policy = self.policy(server)
        if self._closed or not policy or not policy.detection_reporting.enabled or not matches:
            return
        settings = policy.detection_reporting
        now = self.monotonic()
        try:
            batch = instances(
                server, channel, member, chunk, text, matches, times, settings.context_words_per_side, now
            )
        except ValueError:
            self.dropped += len(matches)
            return
        self.dropped += len(matches) - sum(i.count for i in batch)
        for item in batch:
            if not self.permitted(item):
                continue
            if item.size > settings.max_pending_bytes:
                self.dropped += 1
                continue
            self._serial += 1
            item = replace(item, serial=self._serial)
            self.pending.append(item)
            self.due.setdefault(server, now + settings.interval_seconds)
            while (
                sum(i.server == server for i in self.pending) > settings.max_pending_instances
                or sum(i.size for i in self.pending if i.server == server) > settings.max_pending_bytes
            ):
                oldest = next(i for i in self.pending if i.server == server)
                self.pending.remove(oldest)
                self.dropped += 1
            while len(self.pending) > MAX_INSTANCES or self.pending_bytes > MAX_BYTES:
                self.pending.popleft()
                self.dropped += 1
        self.tick()

    def tick(self) -> None:
        now = self.monotonic()
        retained = deque()
        for item in self.pending:
            policy = self.policy(item.server)
            if policy and now - item.queued_at >= policy.detection_reporting.max_pending_age_seconds:
                self.expired += 1
            elif self.permitted(item):
                retained.append(item)
        self.pending = retained
        for key, items in list(self.inflight_items.items()):
            if any(i not in self.pending for i in items):
                task = self.inflight.get(key)
                if task:
                    task.cancel()
        for server in self.config.servers:
            key = server.server_id
            if not any(i.server == key for i in self.pending):
                self.due.pop(key, None)
                self.batches.pop(key, None)
                continue
            if key in self.batches:
                self.batches[key].intersection_update(i.serial for i in self.pending if i.server == key)
                if not self.batches[key]:
                    self.batches.pop(key)
            task = self.tasks.get(key)
            if task is not None and not task.done():
                continue
            if self._closed or self._send is None or now < self.due.get(key, now) or not self._ready(server):
                continue
            self.batches.setdefault(key, {i.serial for i in self.pending if i.server == key})
            self.tasks[key] = asyncio.create_task(self._guarded_flush(server), name=f"detection-feed:{key}")

    async def _guarded_flush(self, server: Server) -> None:
        try:
            await self._flush(server)
        except Exception:
            self.failures += 1
            self.due[server.server_id] = self.monotonic() + 10

    async def _flush(self, server: Server) -> None:
        key = server.server_id
        if server.detection_reporting.interval_seconds == 0:
            self.batches.setdefault(key, set()).update(i.serial for i in self.pending if i.server == key)
        batch = [i for i in self.pending if i.server == key and i.serial in self.batches.get(key, set())]
        pages: list[tuple[str, list[Instance]]] = []
        page, items = HEADER, []
        for item in batch:
            line = render(item, self._name(item.server, item.member), server)
            if units(line) + units(HEADER) + 1 > PAGE_UNITS:
                self.pending.remove(item)
                self.dropped += 1
                continue
            if units(page) + units(line) + 1 > PAGE_UNITS:
                pages.append((page, items))
                page, items = HEADER, []
            page += ("\n" if page else "") + line
            items.append(item)
        if items:
            pages.append((page, items))
        try:
            for page, items in pages[: server.detection_reporting.max_pages_per_flush]:
                if (
                    self._closed
                    or not self._ready(server)
                    or not all(i in self.pending and self.permitted(i) for i in items)
                ):
                    return
                if self._send is None:
                    return
                send = self._send

                async def send_page() -> str:
                    return await send(server, page)

                task = asyncio.create_task(send_page())
                self.inflight[key], self.inflight_items[key] = task, items
                try:
                    await asyncio.wait_for(task, 30)
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        raise
                    return  # privacy cleanup cancelled this specific outbound page
                finally:
                    self.inflight.pop(key, None)
                    self.inflight_items.pop(key, None)
                for item in items:
                    with contextlib.suppress(ValueError):
                        self.pending.remove(item)
                    self.batches.get(key, set()).discard(item.serial)
                self.sent_pages += 1
        except Exception:
            self.failures += 1
            self.due[key] = self.monotonic() + 10
        else:
            if self.batches.get(key):
                self.due[key] = self.monotonic()  # continue the same paginated digest on the next tick
            else:
                self.batches.pop(key, None)
                new = [i.queued_at for i in self.pending if i.server == key]
                self.due[key] = min(new, default=self.monotonic()) + server.detection_reporting.interval_seconds

    async def close(self) -> None:
        self._closed = True
        self.pending.clear()
        for task in (*self.inflight.values(), *self.tasks.values()):
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()
        self.inflight.clear()
        self.inflight_items.clear()
        self.due.clear()
        self.batches.clear()
