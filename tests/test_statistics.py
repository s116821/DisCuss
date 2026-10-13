from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from discuss.calendar import window_at
from discuss.config import Leaderboards
from discuss.lexicon import Lexicon, builtin_words
from discuss.reporting import Scheduler, render, standings
from discuss.storage import Store
from test_config_policy import server


def at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "state.sqlite3")


def test_lexicon_integrity_union_boundaries_and_phrases() -> None:
    builtins = builtin_words()
    assert len(builtins) >= 30
    custom = Lexicon(False, ["VIOLET", "violet", "violet moon", "ＳＨＡＤＥ"])
    assert len(custom.words) == 3
    assert [m.word for m in custom.matches("ultraviolet VIOLET moon, Shade. violet!")] == [
        "violet moon",
        "shade",
        "violet",
    ]
    union = Lexicon(True, ["violet"])
    assert union.words == builtins | {"violet"}
    with pytest.raises(ValueError):
        Lexicon(False, ["!!!"])


def test_idempotent_events_server_isolation_and_minimal_schema(tmp_path: Path) -> None:
    db = store(tmp_path)
    lexicon = Lexicon(False, ["violet"])
    when = at("2026-10-12T12:00:00")
    assert db.ingest("1", "100", "10", "chunk", when, "violet violet private unrelated transcript", lexicon) == 2
    assert db.ingest("1", "100", "10", "chunk", when, "violet", lexicon) == 0
    assert db.ingest("1", "100", "10", "chunk", when, "shade", Lexicon(False, ["shade"])) == 0
    assert db.ingest("2", "100", "10", "chunk", when, "violet", lexicon) == 1
    window = window_at(when, "UTC", "day")
    assert db.counts("1", window.start, window.end) == {"100": {"violet": 2}}
    assert db.counts("2", window.start, window.end) == {"100": {"violet": 1}}
    columns = {r[1] for r in db.db.execute("PRAGMA table_info(events)")}
    assert not {"audio", "transcript", "token"} & columns
    assert "private unrelated transcript" not in "\n".join(db.db.iterdump())
    db.close()


def test_exposure_union_silence_health_restart_and_opt_out(tmp_path: Path) -> None:
    db = store(tmp_path)
    start = at("2026-10-12T12:00:00")
    db.monitor("a", "1", "10", ["100"], start)
    db.monitor("a", "1", "10", ["100"], start + timedelta(minutes=10))
    db.monitor("b", "1", "20", ["100"], start + timedelta(minutes=5))
    db.monitor("b", "1", "20", ["100"], start + timedelta(minutes=15))
    db.monitor("a", "1", "10", [], start + timedelta(minutes=10), healthy=False)
    assert db.durations("1", start, start + timedelta(hours=1)) == {"100": 900}
    db.close()
    db = store(tmp_path)
    db.recover()
    assert db.durations("1", start, start + timedelta(hours=2)) == {"100": 900}
    db.monitor("a", "1", "10", ["100"], start + timedelta(hours=1))
    db.monitor("a", "1", "10", ["100"], start + timedelta(hours=1, minutes=5))
    db.set_opt_out("1", "100", True, start + timedelta(hours=1, minutes=5))
    db.monitor("a", "1", "10", ["100"], start + timedelta(hours=1, minutes=10))
    assert db.durations("1", start, start + timedelta(hours=2)) == {"100": 1200}
    assert db.ingest("1", "100", "10", "blocked", start, "violet", Lexicon(False, ["violet"])) == 0
    db.close()


def test_calendar_dst_windows_and_scaled_qualification(tmp_path: Path) -> None:
    spring = window_at(at("2026-03-08T18:00:00"), "America/Chicago", "day")
    fall = window_at(at("2026-11-01T18:00:00"), "America/Chicago", "day")
    assert (spring.end - spring.start).total_seconds() == 23 * 3600
    assert (fall.end - fall.start).total_seconds() == 25 * 3600
    db = store(tmp_path)
    start = at("2026-10-12T12:00:00")
    lexicon = Lexicon(False, ["violet"])
    for member, minutes, text in [("100", 60, "violet violet"), ("200", 10, "violet"), ("300", 30, "")]:
        db.monitor(member, "1", "10", [member], start)
        db.monitor(member, "1", "10", [], start + timedelta(minutes=minutes))
        db.ingest("1", member, "10", member, start, text, lexicon)
    window = window_at(start, "UTC", "week")
    settings = Leaderboards()
    board = standings(db, "1", window, settings)
    assert [r.member_id for r in board.total] == ["100", "200"]
    assert [r.member_id for r in board.scaled] == ["100", "300"]
    assert board.scaled[0].rate == 2 and board.scaled[1].rate == 0
    settings.sort_order = "ascending"
    assert [r.member_id for r in standings(db, "1", window, settings).scaled] == ["300", "100"]
    next_week = window_at(start + timedelta(days=7), "UTC", "week")
    assert not standings(db, "1", next_week, settings).total
    db.close()


def test_outbox_retry_catchup_and_year_overlap_retention(tmp_path: Path) -> None:
    db = store(tmp_path)
    policy = server()
    lexicon = Lexicon(False, ["violet"])
    december = at("2025-12-31T12:00:00")
    january = at("2026-01-01T01:00:00")
    db.ingest("1", "100", "10", "december", december, "violet", lexicon)
    db.monitor("a", "1", "10", ["100"], december)
    db.monitor("a", "1", "10", [], december + timedelta(hours=1))
    scheduler = Scheduler(db)
    assert scheduler.queue_due(policy, january) == 2  # month and year, week remains open
    assert scheduler.queue_due(policy, january) == 0
    assert not scheduler.prune(policy, january)  # queued reports protect their data

    sent = []
    fail = True

    async def send(page: str, period: str, index: int) -> str:
        nonlocal fail
        if fail:
            fail = False
            raise RuntimeError("Synthetic transport failure before send")
        sent.append((period, index))
        return str(len(sent))

    async def retry() -> None:
        with pytest.raises(RuntimeError):
            await scheduler.deliver("1", send)
        assert await scheduler.deliver("1", send) >= 2
        assert await scheduler.deliver("1", send) == 0

    asyncio.run(retry())
    assert scheduler.prune(policy, january)
    week = window_at(january, "UTC", "week")
    assert db.counts("1", week.start, week.end) == {"100": {"violet": 1}}
    assert db.durations("1", week.start, week.end) == {"100": 3600}
    db.ingest("1", "100", "10", "january", january, "violet", lexicon)
    assert scheduler.queue_due(policy, at("2026-01-05T00:00:00")) == 1
    assert len(sent) == len(set(sent))
    db.close()


def test_render_pages_delete_backup_and_all_disabled_retention(tmp_path: Path) -> None:
    db = store(tmp_path)
    when = at("2026-10-12T12:00:00")
    lexicon = Lexicon(False, ["violet"])
    for member in range(1, 101):
        db.ingest("1", str(member), "10", "chunk", when, "violet", lexicon)
    window = window_at(when, "UTC", "day")
    pages = render(window, standings(db, "1", window, Leaderboards()), member_name=lambda m: "Player-" + m, limit=512)
    assert len(pages) > 1 and all(len(p) <= 512 for p in pages)
    assert "Player-100" in "\n".join(pages) and "Member 100" not in "\n".join(pages)
    backup = tmp_path / "backup.sqlite3"
    db.backup(backup)
    with sqlite3.connect(backup) as copy:
        assert copy.execute("SELECT count(*) FROM events").fetchone()[0] == 100
    db.delete_member("1", "100")
    assert "100" not in db.counts("1", window.start, window.end)
    policy = server()
    for cadence in ("day", "week", "month", "year"):
        setattr(policy.leaderboards.reports, cadence, False)
    assert Scheduler(db).prune(policy, when + timedelta(days=31))
    assert db.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    db.close()


def test_empty_daily_suppression_and_transactional_cursor(tmp_path: Path) -> None:
    db = store(tmp_path)
    policy = server()
    policy.leaderboards.reports.day = True
    policy.leaderboards.suppress_empty_reports = False
    first = at("2026-10-12T12:00:00")
    db.ingest("1", "100", "10", "empty", first, "no tracked entry", Lexicon(False, ["violet"]))
    assert Scheduler(db).queue_due(policy, first + timedelta(days=1)) == 0
    assert db.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
    db.close()


def test_partial_page_acknowledgement_and_concurrent_retry(tmp_path: Path) -> None:
    db = store(tmp_path)
    scheduler = Scheduler(db)
    with db.db:
        db.db.execute(
            "INSERT INTO outbox(server,period,start,end,pages,members) VALUES (?,?,?,?,?,?)",
            ("1", "fixture", 0, 1, json.dumps(["one", "two", "three"]), "[]"),
        )
    sent = []
    failed = False

    async def send(page: str, period: str, index: int) -> str:
        nonlocal failed
        await asyncio.sleep(0)
        if index == 1 and not failed:
            failed = True
            raise RuntimeError("Synthetic failure before second send")
        sent.append(page)
        return str(len(sent))

    async def run() -> None:
        with pytest.raises(RuntimeError):
            await scheduler.deliver("1", send)
        assert sent == ["one"]
        result = await asyncio.gather(scheduler.deliver("1", send), scheduler.deliver("1", send))
        assert sorted(result) == [0, 2]
        assert sent == ["one", "two", "three"]

    asyncio.run(run())
    db.close()


def test_failed_migration_is_atomic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("discuss.storage.SCHEMA", "CREATE TABLE partial(value TEXT); INVALID SQL;")
    path = tmp_path / "failed.sqlite3"
    with pytest.raises(ValueError, match="migration failed"):
        Store(path)
    with sqlite3.connect(path) as database:
        assert database.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
