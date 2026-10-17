"""Minimal SQLite events, monitoring checkpoints and durable report state."""

from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from .calendar import from_microseconds, utc_microseconds
from .config import check_private_file
from .lexicon import Lexicon

SCHEMA = """
CREATE TABLE chunks (
 server TEXT NOT NULL, member TEXT NOT NULL, chunk TEXT NOT NULL, at INTEGER NOT NULL,
 PRIMARY KEY(server,member,chunk));
CREATE TABLE events (
 server TEXT NOT NULL, member TEXT NOT NULL, channel TEXT NOT NULL, chunk TEXT NOT NULL,
 ordinal INTEGER NOT NULL, word TEXT NOT NULL, at INTEGER NOT NULL,
 PRIMARY KEY(server,member,chunk,ordinal));
CREATE INDEX events_period ON events(server,at,member,word);
CREATE TABLE exposure (
 id INTEGER PRIMARY KEY, server TEXT NOT NULL, member TEXT NOT NULL,
 channel TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL CHECK(end>=start));
CREATE INDEX exposure_period ON exposure(server,member,start,end);
CREATE TABLE leases (
 listener TEXT NOT NULL, server TEXT NOT NULL, member TEXT NOT NULL, channel TEXT NOT NULL,
 start INTEGER NOT NULL, checkpoint INTEGER NOT NULL,
 PRIMARY KEY(listener,server,member));
CREATE TABLE preferences (
 server TEXT NOT NULL, member TEXT NOT NULL, opted_out INTEGER NOT NULL,
 PRIMARY KEY(server,member));
CREATE TABLE cursors (
 server TEXT NOT NULL, cadence TEXT NOT NULL, next_start INTEGER NOT NULL,
 PRIMARY KEY(server,cadence));
CREATE TABLE outbox (
 server TEXT NOT NULL, period TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
 pages TEXT NOT NULL, members TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(server,period));
CREATE TABLE receipts (
 server TEXT NOT NULL, period TEXT NOT NULL, page INTEGER NOT NULL, message TEXT NOT NULL,
 PRIMARY KEY(server,period,page));
PRAGMA user_version=1;
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        elif os.name != "nt" and path.stat().st_mode & 0o077:
            raise ValueError("Restrict statistics file permissions to 0600")
        check_private_file(path)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            try:
                self.db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            except sqlite3.Error:
                self.db.rollback()
                self.db.close()
                raise ValueError("Statistics schema migration failed") from None
            version = 1
        if version == 1:
            try:
                self.db.executescript(
                    "BEGIN IMMEDIATE; CREATE TABLE controls "
                    "(server TEXT PRIMARY KEY, disabled INTEGER NOT NULL); "
                    "PRAGMA user_version=2; COMMIT;"
                )
            except sqlite3.Error:
                self.db.rollback()
                self.db.close()
                raise ValueError("Statistics schema migration failed") from None
        elif version != 2:
            self.db.close()
            raise ValueError("Unsupported statistics schema version")

    def close(self) -> None:
        self.db.close()

    def detection_members(self, server: str, start: datetime, end: datetime) -> set[str]:
        return {
            row[0]
            for row in self.db.execute(
                "SELECT DISTINCT member FROM events WHERE server=? AND at>=? AND at<?",
                (server, utc_microseconds(start), utc_microseconds(end)),
            )
        }

    def disabled(self, server: str) -> bool:
        row = self.db.execute("SELECT disabled FROM controls WHERE server=?", (server,)).fetchone()
        return row is not None and bool(row[0])

    def set_disabled(self, server: str, disabled: bool) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO controls VALUES (?,?)", (server, int(disabled)))

    def opted_out(self, server: str, member: str) -> bool:
        row = self.db.execute(
            "SELECT opted_out FROM preferences WHERE server=? AND member=?", (server, member)
        ).fetchone()
        return row is not None and bool(row[0])

    def set_opt_out(self, server: str, member: str, enabled: bool, at: datetime) -> None:
        stamp = utc_microseconds(at)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES (?,?,?)", (server, member, int(enabled)))
            if enabled:
                rows = self.db.execute("SELECT * FROM leases WHERE server=? AND member=?", (server, member)).fetchall()
                for row in rows:
                    self._close_lease(row, min(stamp, row["checkpoint"]))
                self.db.execute("DELETE FROM leases WHERE server=? AND member=?", (server, member))

    def ingest(
        self,
        server: str,
        member: str,
        channel: str,
        chunk: str,
        at: datetime,
        text: str,
        lexicon: Lexicon,
        *,
        excluded: bool = False,
        detection_times: list[datetime] | None = None,
    ) -> int:
        stamp = utc_microseconds(at)
        with self.db:
            result = self.db.execute("INSERT OR IGNORE INTO chunks VALUES (?,?,?,?)", (server, member, chunk, stamp))
            if result.rowcount == 0 or excluded or self.opted_out(server, member):
                return 0
            matches = lexicon.matches(text)
            if detection_times is not None and len(detection_times) != len(matches):
                raise ValueError("Detection timing must match recognized tracked entries")
            self.db.executemany(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        server,
                        member,
                        channel,
                        chunk,
                        i,
                        m.word,
                        utc_microseconds(detection_times[i]) if detection_times is not None else stamp,
                    )
                    for i, m in enumerate(matches)
                ],
            )
            return len(matches)

    def _close_lease(self, row: sqlite3.Row, end: int) -> None:
        if end > row["start"]:
            self.db.execute(
                "INSERT INTO exposure(server,member,channel,start,end) VALUES (?,?,?,?,?)",
                (row["server"], row["member"], row["channel"], row["start"], end),
            )

    def monitor(
        self,
        listener: str,
        server: str,
        channel: str,
        members: Iterable[str],
        at: datetime,
        *,
        healthy: bool = True,
        excluded: Iterable[str] = (),
    ) -> None:
        """Checkpoint actual healthy occupancy. Call with no members to end listening."""
        stamp = utc_microseconds(at)
        blocked = set(excluded)
        active = {m for m in members if m not in blocked and not self.opted_out(server, m)} if healthy else set()
        with self.db:
            existing = self.db.execute(
                "SELECT * FROM leases WHERE listener=? AND server=?", (listener, server)
            ).fetchall()
            for row in existing:
                if stamp < row["checkpoint"]:
                    raise ValueError("Monitoring checkpoints must be monotonic")
                if row["member"] not in active or row["channel"] != channel:
                    self._close_lease(row, stamp if healthy else row["checkpoint"])
                    self.db.execute(
                        "DELETE FROM leases WHERE listener=? AND server=? AND member=?",
                        (listener, server, row["member"]),
                    )
                else:
                    self.db.execute(
                        "UPDATE leases SET checkpoint=? WHERE listener=? AND server=? AND member=?",
                        (stamp, listener, server, row["member"]),
                    )
            for member in active:
                self.db.execute(
                    "INSERT OR IGNORE INTO leases VALUES (?,?,?,?,?,?)",
                    (listener, server, member, channel, stamp, stamp),
                )

    def recover(self) -> None:
        """Do not infer exposure between the last durable heartbeat and a restart."""
        with self.db:
            for row in self.db.execute("SELECT * FROM leases").fetchall():
                self._close_lease(row, row["checkpoint"])
            self.db.execute("DELETE FROM leases")

    def counts(self, server: str, start: datetime, end: datetime) -> dict[str, dict[str, int]]:
        lower, upper = utc_microseconds(start), utc_microseconds(end)
        result: dict[str, dict[str, int]] = defaultdict(dict)
        for row in self.db.execute(
            "SELECT member,word,count(*) AS n FROM events WHERE server=? AND at>=? AND at<? GROUP BY member,word",
            (server, lower, upper),
        ):
            result[row["member"]][row["word"]] = row["n"]
        return dict(result)

    def durations(self, server: str, start: datetime, end: datetime) -> dict[str, float]:
        lower, upper = utc_microseconds(start), utc_microseconds(end)
        spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
        sql = (
            "SELECT member,start,end FROM exposure WHERE server=? AND start<? AND end>? "
            "UNION ALL SELECT member,start,checkpoint AS end FROM leases WHERE server=? AND start<? AND checkpoint>?"
        )
        for row in self.db.execute(sql, (server, upper, lower, server, upper, lower)):
            spans[row["member"]].append((max(lower, row["start"]), min(upper, row["end"])))
        result = {}
        for member, intervals in spans.items():
            intervals.sort()
            left, right = intervals[0]
            total = 0
            for a, b in intervals[1:]:
                if a <= right:
                    right = max(right, b)
                else:
                    total += right - left
                    left, right = a, b
            result[member] = (total + right - left) / 1000000
        return result

    def first_observation(self, server: str) -> datetime | None:
        row = self.db.execute(
            "SELECT min(at) FROM (SELECT at FROM chunks WHERE server=? "
            "UNION ALL SELECT start AS at FROM exposure WHERE server=? "
            "UNION ALL SELECT start AS at FROM leases WHERE server=?)",
            (server, server, server),
        ).fetchone()
        return from_microseconds(row[0]) if row[0] is not None else None

    def delete_member(self, server: str, member: str) -> None:
        with self.db:
            for table in ("events", "chunks", "exposure", "leases", "preferences"):
                self.db.execute(f"DELETE FROM {table} WHERE server=? AND member=?", (server, member))
            for row in self.db.execute("SELECT period,members FROM outbox WHERE server=?", (server,)).fetchall():
                if member in json.loads(row["members"]):
                    self.db.execute("DELETE FROM receipts WHERE server=? AND period=?", (server, row["period"]))
                    self.db.execute("DELETE FROM outbox WHERE server=? AND period=?", (server, row["period"]))

    def backup(self, destination: Path) -> None:
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ValueError("Backup destination must be a new file")
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        check_private_file(destination)
        with sqlite3.connect(destination) as target:
            self.db.backup(target)

    def prune(self, server: str, before: datetime) -> bool:
        cutoff = utc_microseconds(before)
        pending = self.db.execute(
            "SELECT 1 FROM outbox WHERE server=? AND delivered=0 AND start<? LIMIT 1", (server, cutoff)
        ).fetchone()
        if pending:
            return False
        with self.db:
            self.db.execute("DELETE FROM events WHERE server=? AND at<?", (server, cutoff))
            self.db.execute("DELETE FROM chunks WHERE server=? AND at<?", (server, cutoff))
            self.db.execute("DELETE FROM exposure WHERE server=? AND end<=?", (server, cutoff))
            self.db.execute("DELETE FROM leases WHERE server=? AND checkpoint<?", (server, cutoff))
            self.db.execute("UPDATE exposure SET start=? WHERE server=? AND start<?", (cutoff, server, cutoff))
            self.db.execute(
                "UPDATE leases SET start=? WHERE server=? AND start<? AND checkpoint>=?",
                (cutoff, server, cutoff, cutoff),
            )
            for row in self.db.execute(
                "SELECT period FROM outbox WHERE server=? AND delivered=1 AND end<=?", (server, cutoff)
            ).fetchall():
                self.db.execute("DELETE FROM receipts WHERE server=? AND period=?", (server, row["period"]))
                self.db.execute("DELETE FROM outbox WHERE server=? AND period=?", (server, row["period"]))
        return True
