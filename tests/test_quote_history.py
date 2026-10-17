from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import discord
import pytest

from discuss.discord_adapter import DiscordListener
from discuss.lexicon import Lexicon
from discuss.quote_history import belongs, bounds, parse_line
from discuss.speech import SpeechPipeline
from discuss.storage import Store
from test_detection_reporting import configured

NOW = datetime(2026, 10, 17, 23, tzinfo=UTC)


def test_time_bounds_and_dst():
    start, end = bounds(None, None, "America/Chicago", NOW)
    assert end - start == timedelta(days=7)
    assert bounds("2026-10-17", None, "America/Chicago", NOW)[0].hour == 5
    for since, until in [("invalid", None), ("2020-01-01", None), (None, "2099-01-01"), ("2026-11-01T01:30", None)]:
        with pytest.raises(ValueError):
            bounds(since, until, "America/Chicago", NOW)
    a = parse_line(
        "“**violet**” — [Old name](https://discord.com/users/100), November 1, 2026 @ 1:30 am CDT", "America/Chicago"
    )
    b = parse_line(
        "“**violet**” — [Old name](https://discord.com/users/100), November 1, 2026 @ 1:30 am CST", "America/Chicago"
    )
    assert a and b and b[2] - a[2] == timedelta(hours=1)
    assert parse_line("“text” — Somebody, February 31, 2026 @ 5:00 pm CST", "America/Chicago") is None
    assert parse_line("“text” — Somebody, March 8, 2026 @ 2:30 am CST", "America/Chicago") is None


def test_legacy_requires_unique_minimal_metadata_not_name_alone(tmp_path):
    store = Store(tmp_path / "statistics.sqlite3")
    at = NOW.replace(second=0)
    assert not belongs("Stark", at, "100", "Stark", store, "1")
    store.ingest("1", "100", "10", "a", at, "violet", Lexicon(False, ["violet"]))
    assert belongs("Stark", at, "100", "Stark", store, "1")
    assert not belongs("Stark", at, "200", "Stark", store, "1")
    store.ingest("1", "200", "10", "b", at, "violet", Lexicon(False, ["violet"]))
    assert not belongs("Stark", at, "100", "Stark", store, "1")
    assert belongs("[Old name](https://discord.com/users/100)", at, "100", "New name", store, "1")
    store.close()


def test_bounded_own_bot_history_and_requester_access(tmp_path):
    async def run():
        cfg = configured()
        server = cfg.servers[0]
        server.leaderboards.timezone = "UTC"
        store = Store(tmp_path / "statistics.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        listener = DiscordListener(cfg.bots[0], cfg, store, pipeline)
        listener.client._connection.user = SimpleNamespace(id=999)
        channel = Mock(spec=discord.TextChannel)
        access = SimpleNamespace(view_channel=True, send_messages=True, read_message_history=True)
        channel.permissions_for.return_value = access
        guild = SimpleNamespace(me=object(), get_channel=lambda c: channel, get_member=lambda m: object())
        listener.client.get_guild = Mock(return_value=guild)
        seen = []
        line = "“**violet**” — [Old name](https://discord.com/users/100), October 17, 2026 @ 5:00 pm UTC"

        async def history(**kwargs):
            seen.append(kwargs)
            for author, text in [(123, line), (999, "malformed"), (999, line.replace("/100)", "/200)")), (999, line)]:
                yield SimpleNamespace(
                    author=SimpleNamespace(id=author), content=text, jump_url="https://discord.com/channels/1/50/123"
                )

        channel.history = history
        interaction = SimpleNamespace(guild=guild, user=SimpleNamespace(id=100))
        member = SimpleNamespace(id=100, display_name="New name")
        pages = await listener.quote_pages(interaction, server, member, "2026-10-17T00:00Z", "2026-10-17T18:00Z")
        assert sum(p.count("original report") for p in pages) == 1 and "New name" in pages[0]
        assert seen[0]["limit"] == 2000
        assert "violet" not in " ".join(store.db.iterdump())
        access.read_message_history = False
        assert "Read Message History" in (await listener.quote_pages(interaction, server, member, None, None))[0]
        assert len(seen) == 1
        await listener.close()
        await pipeline.close()
        store.close()

    asyncio.run(run())
