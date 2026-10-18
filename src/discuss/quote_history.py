"""Bounded parsing of our published Discord reports, with no local quote archive."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .detection_reporting import MONTHS, safe_text
from .storage import Store

SCAN_LIMIT = 2000
RESULT_LIMIT = 20
LINE = re.compile(
    r"^“(?P<quote>.+)” — (?P<speaker>.+), (?P<month>[A-Za-z]+) (?P<day>\d{1,2}), "
    r"(?P<year>\d{4}) @ (?P<hour>\d{1,2}):(?P<minute>\d{2}) (?P<ampm>am|pm) (?P<zone>[\w+:-]+)$"
)
PROFILE = re.compile(r"^\[.+\]\(https://discord\.com/users/(?P<member>\d+)\)$")


def bounds(since: str | None, until: str | None, timezone: str, now: datetime) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)

    def parse(value: str | None, default: datetime) -> datetime:
        if not value:
            return default
        try:
            result = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Use ISO dates/times, for example 2026-10-17 or 2026-10-17T14:30-05:00.") from None
        if result.tzinfo is None:
            result = result.replace(tzinfo=zone)
            if result.utcoffset() != result.replace(fold=1).utcoffset():
                raise ValueError("This local time crosses a clock change; include an explicit UTC offset.")
        return result.astimezone(UTC)

    end = parse(until, now)
    start = parse(since, end - timedelta(days=7))
    if start >= end or end - start > timedelta(days=366) or end > now + timedelta(minutes=1):
        raise ValueError("Choose a past time range longer than zero and at most 366 days; until is exclusive.")
    return start, end


def parse_line(line: str, timezone: str) -> tuple[str, str, datetime] | None:
    match = LINE.fullmatch(line)
    if not match or match["month"] not in MONTHS:
        return None
    hour = int(match["hour"])
    if not 1 <= hour <= 12:
        return None
    try:
        local = datetime(
            int(match["year"]),
            MONTHS.index(match["month"]) + 1,
            int(match["day"]),
            hour % 12 + (12 if match["ampm"] == "pm" else 0),
            int(match["minute"]),
            tzinfo=ZoneInfo(timezone),
        )
    except ValueError:
        return None
    for fold in (0, 1):
        candidate = local.replace(fold=fold)
        if candidate.tzname() == match["zone"] and candidate.astimezone(UTC).astimezone(candidate.tzinfo) == candidate:
            return match["quote"], match["speaker"], candidate.astimezone(UTC)
    return None


def belongs(speaker: str, at: datetime, member: str, display_name: str, store: Store, server: str) -> bool:
    profile = PROFILE.fullmatch(speaker)
    if profile:
        return profile["member"] == member
    # Plain display names are mutable/non-unique: require the retained minimal
    # detection metadata to identify exactly this member in the displayed minute.
    return speaker == safe_text(display_name, 64) and store.detection_members(
        server, at, at + timedelta(minutes=1)
    ) == {member}
