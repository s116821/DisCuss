"""Half-open UTC windows derived from local calendar boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

Cadence = Literal["day", "week", "month", "year"]


def aware(instant: datetime) -> datetime:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("An aware timestamp is required")
    return instant.astimezone(UTC)


def utc_microseconds(instant: datetime) -> int:
    delta = aware(instant) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def from_microseconds(value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=value)


def midnight(day: date, zone: ZoneInfo) -> datetime:
    candidate = datetime.combine(day, time.min, zone)
    # Resolve skipped local midnights forward; fold=0 selects the first ambiguous boundary.
    for _ in range(2881):
        converted = candidate.astimezone(UTC)
        if converted.astimezone(zone).replace(tzinfo=None) == candidate.replace(tzinfo=None):
            return converted
        candidate += timedelta(minutes=1)
    raise ValueError("Reporting timezone has no resolvable boundary")


@dataclass(frozen=True, slots=True)
class Window:
    cadence: Cadence
    start: datetime
    end: datetime

    @property
    def identity(self) -> str:
        return f"{self.cadence}:{self.start.isoformat()}"


def window_at(instant: datetime, timezone: str, cadence: Cadence) -> Window:
    day = aware(instant).astimezone(ZoneInfo(timezone)).date()
    if cadence == "day":
        start, end = day, day + timedelta(days=1)
    elif cadence == "week":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
    elif cadence == "month":
        start = day.replace(day=1)
        end = date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)
    elif cadence == "year":
        start, end = date(day.year, 1, 1), date(day.year + 1, 1, 1)
    else:
        raise ValueError("Unknown reporting cadence")
    zone = ZoneInfo(timezone)
    return Window(cadence, midnight(start, zone), midnight(end, zone))
