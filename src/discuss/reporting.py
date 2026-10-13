"""Window-specific analytics, bounded rendering and restart-safe outbox."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from .calendar import Cadence, Window, from_microseconds, utc_microseconds, window_at
from .config import Leaderboards, Server
from .detection_reporting import MONTHS, safe_text, units
from .storage import Store


@dataclass(frozen=True, slots=True)
class Rank:
    member_id: str
    count: int
    monitored_seconds: float
    rate: float | None


@dataclass(frozen=True, slots=True)
class Standings:
    total: tuple[Rank, ...]
    scaled: tuple[Rank, ...]
    words: dict[str, dict[str, int]]


def standings(store: Store, server: str, window: Window, settings: Leaderboards) -> Standings:
    counts = store.counts(server, window.start, window.end)
    duration = store.durations(server, window.start, window.end)
    total, scaled = [], []
    for member in set(counts) | set(duration):
        count = sum(counts.get(member, {}).values())
        seconds = duration.get(member, 0.0)
        rank = Rank(member, count, seconds, count * 3600 / seconds if seconds > 0 else None)
        if count:
            total.append(rank)
        if settings.scaled.enabled and seconds > 0 and seconds >= settings.scaled.minimum_monitored_seconds:
            scaled.append(rank)
    descending = settings.sort_order == "descending"
    total.sort(key=lambda row: (-row.count if descending else row.count, int(row.member_id)))
    scaled.sort(key=lambda row: (-(row.rate or 0) if descending else (row.rate or 0), int(row.member_id)))
    return Standings(tuple(total), tuple(scaled), counts)


def safe_word(word: str) -> str:
    result = word.replace("@", "@\u200b")
    for char in "\\" + chr(96) + "*_~|<>":
        result = result.replace(char, "\\" + char)
    return result


MEMBER_SLOT = re.compile(r"\{\{member:([1-9][0-9]{0,19})\}\} *")
LEGACY_MEMBER = re.compile(r"\bMember ([1-9][0-9]{0,19})\b")
NAME_UNITS = 132


def period_label(window: Window, timezone: str = "UTC") -> str:
    start = window.start.astimezone(ZoneInfo(timezone))
    end = (window.end - timedelta(microseconds=1)).astimezone(ZoneInfo(timezone))
    if window.cadence == "year":
        return str(start.year)
    if window.cadence == "month":
        return f"{MONTHS[start.month - 1]} {start.year}"
    first = f"{MONTHS[start.month - 1][:3]} {start.day}"
    if window.cadence == "day":
        return f"{first}, {start.year}"
    if start.year != end.year:
        return f"{first}, {start.year} – {MONTHS[end.month - 1][:3]} {end.day}, {end.year}"
    last = str(end.day) if start.month == end.month else f"{MONTHS[end.month - 1][:3]} {end.day}"
    return f"{first}–{last}, {start.year}"


def report_members(page: str) -> set[str]:
    return {m.group(1) for pattern in (MEMBER_SLOT, LEGACY_MEMBER) for m in pattern.finditer(page)}


def resolve_page_names(page: str, name: Callable[[str], str], *, limit: int = 1900) -> str:
    # Keep old page/receipt identities while removing their automatic word sections.
    lines = [
        line
        for line in page.splitlines()
        if line != "Per-word counts" and not re.match(r"^Member [0-9]+: .+ = [0-9]+$", line)
    ]
    template = "\n".join(lines)
    for width in (64, 32, 16, 8, 4, 2, 1):
        rendered = re.sub(
            r"\{\{member:([1-9][0-9]{0,19})\}\} *|\bMember ([1-9][0-9]{0,19})\b",
            lambda m: safe_text(name(m.group(1) or m.group(2)) or "Unknown member", width),
            template,
        )
        if units(rendered) <= limit:
            return rendered
    raise ValueError("Report page cannot fit the message limit")


def render(
    window: Window,
    board: Standings,
    *,
    member_name: Callable[[str], str] | None = None,
    timezone: str = "UTC",
    show_scaled: bool = True,
    reserve_names: bool = False,
    limit: int = 1900,
) -> list[str]:
    if not 256 <= limit <= 1900:
        raise ValueError("Report page limit must be between 256 and 1900")
    title = {"day": "Daily", "week": "Weekly", "month": "Monthly", "year": "Yearly"}[window.cadence]
    header = f"**{title} standings**\n{period_label(window, timezone)}"

    def label(member: str) -> str:
        if reserve_names:
            return f"{{{{member:{member}}}}}".ljust(NAME_UNITS)
        return safe_text(member_name(member) if member_name else "Unknown member", 64)

    sections = [
        (
            "Total cusses",
            [f"{i}. **{label(r.member_id)}** · **{r.count:,}**" for i, r in enumerate(board.total, 1)]
            or ["No cusses detected in this period."],
        )
    ]
    if show_scaled:
        rows = [
            f"{i}. **{label(r.member_id)}** · **{r.rate:,.2f}/hr**\n"
            f"   {r.count:,} cusses · {r.monitored_seconds / 60:,.1f}m monitored"
            for i, r in enumerate(board.scaled, 1)
        ]
        sections.append(("Cusses per monitored hour", rows or ["No members meet the monitoring threshold yet."]))
    pages, current = [], header
    for heading, rows in sections:
        section = f"**{heading}**"
        if units(current + "\n\n" + section + "\n" + rows[0]) > limit:
            pages.append(current)
            current = header
        current += "\n\n" + section
        for line in rows:
            if units(header + "\n\n" + section + "\n" + line) > limit:
                raise ValueError("A report row exceeds the page limit")
            if units(current + "\n" + line) > limit:
                pages.append(current)
                current = header + "\n\n" + section
            current += "\n" + line
    pages.append(current)
    return pages


def render_word_counts(
    window: Window, counts: dict[str, int], speaker: str, timezone: str, *, limit: int = 1900
) -> list[str]:
    header = f"**{safe_text(speaker, 64)} — word counts**\n{period_label(window, timezone)}"
    pages, current = [], header
    rows = [f"**{safe_text(word, 100)}** · {count:,}" for word, count in sorted(counts.items())] or [
        "No tracked detections in this period."
    ]
    for row in rows:
        if units(current + "\n" + row) > limit:
            pages.append(current)
            current = header
        current += "\n" + row
    pages.append(current)
    return pages


class Scheduler:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._delivery_locks: dict[str, asyncio.Lock] = {}

    def queue_due(self, server: Server, now: datetime, *, max_windows: int = 1000) -> int:
        """Queue closed windows and advance each cursor in the same transaction."""
        queued = 0
        enabled = server.leaderboards.reports.enabled_periods()
        first = self.store.first_observation(server.server_id) or now
        with self.store.db:
            for name in ("day", "week", "month", "year"):
                cadence = name
                current = window_at(now, server.leaderboards.timezone, cadence)
                row = self.store.db.execute(
                    "SELECT next_start FROM cursors WHERE server=? AND cadence=?", (server.server_id, name)
                ).fetchone()
                if name not in enabled:
                    self.store.db.execute(
                        "INSERT OR REPLACE INTO cursors VALUES (?,?,?)",
                        (server.server_id, name, utc_microseconds(current.start)),
                    )
                    continue
                next_start = (
                    from_microseconds(row[0])
                    if row
                    else (window_at(first, server.leaderboards.timezone, cadence).start)
                )
                steps = 0
                window = window_at(next_start, server.leaderboards.timezone, cadence)
                while window.end <= now and steps < max_windows:
                    board = standings(self.store, server.server_id, window, server.leaderboards)
                    suppress = not board.words and (name == "day" or server.leaderboards.suppress_empty_reports)
                    if not suppress:
                        pages = render(
                            window,
                            board,
                            timezone=server.leaderboards.timezone,
                            show_scaled=server.leaderboards.scaled.enabled,
                            reserve_names=True,
                        )
                        members = sorted({r.member_id for r in board.total + board.scaled}, key=int)
                        result = self.store.db.execute(
                            "INSERT OR IGNORE INTO outbox(server,period,start,end,pages,members) VALUES (?,?,?,?,?,?)",
                            (
                                server.server_id,
                                window.identity,
                                utc_microseconds(window.start),
                                utc_microseconds(window.end),
                                json.dumps(pages),
                                json.dumps(members),
                            ),
                        )
                        queued += int(result.rowcount > 0)
                    next_start = window.end
                    window = window_at(next_start, server.leaderboards.timezone, cadence)
                    steps += 1
                self.store.db.execute(
                    "INSERT OR REPLACE INTO cursors VALUES (?,?,?)",
                    (server.server_id, name, utc_microseconds(next_start)),
                )
        return queued

    async def deliver(self, server: str, send: Callable[[str, str, int], Awaitable[str]]) -> int:
        """Send pending pages; provider lost-ack ambiguity remains at-least-once."""
        lock = self._delivery_locks.setdefault(server, asyncio.Lock())
        async with lock:
            return await self._deliver(server, send)

    async def _deliver(self, server: str, send: Callable[[str, str, int], Awaitable[str]]) -> int:
        sent = 0
        for row in self.store.db.execute(
            "SELECT * FROM outbox WHERE server=? AND delivered=0 ORDER BY end,period", (server,)
        ).fetchall():
            for index, page in enumerate(json.loads(row["pages"])):
                live = self.store.db.execute(
                    "SELECT 1 FROM outbox WHERE server=? AND period=? AND delivered=0", (server, row["period"])
                ).fetchone()
                if live is None:
                    break
                known = self.store.db.execute(
                    "SELECT 1 FROM receipts WHERE server=? AND period=? AND page=?", (server, row["period"], index)
                ).fetchone()
                if known:
                    continue
                message = await send(page, row["period"], index)
                with self.store.db:
                    self.store.db.execute(
                        "INSERT OR IGNORE INTO receipts VALUES (?,?,?,?)", (server, row["period"], index, message)
                    )
                sent += 1
            with self.store.db:
                self.store.db.execute(
                    "UPDATE outbox SET delivered=1,pages='[]',members='[]' WHERE server=? AND period=?",
                    (server, row["period"]),
                )
        return sent

    def prune(self, server: Server, now: datetime) -> bool:
        enabled = server.leaderboards.reports.enabled_periods()
        if enabled:
            cutoff = min(window_at(now, server.leaderboards.timezone, cast(Cadence, name)).start for name in enabled)
        else:
            cutoff = now - timedelta(days=server.leaderboards.retention_days_when_reports_disabled)
        return self.store.prune(server.server_id, cutoff)
