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


def test_time_only_uses_server_today_and_honors_offsets():
    start, end = bounds("14:30", "15:45", "America/Chicago", NOW)
    assert start == NOW.replace(hour=19, minute=30) and end == NOW.replace(hour=20, minute=45)
    start, end = bounds("14:30-07:00", "15:45-07:00", "America/Chicago", NOW)
    assert start == NOW.replace(hour=21, minute=30) and end == NOW.replace(hour=22, minute=45)
    # UTC and the supplied offset are already on the 18th; server-local today is still the 17th.
    midnight = datetime(2026, 10, 18, 0, 30, tzinfo=UTC)
    assert bounds("14:30+09:00", None, "America/Chicago", midnight)[0] == NOW.replace(hour=5, minute=30)
    assert bounds("06:30", None, "Asia/Tokyo", NOW)[0] == NOW.replace(hour=21, minute=30)
    assert bounds("14:30:15.125Z", None, "UTC", NOW)[0] == NOW.replace(
        hour=14, minute=30, second=15, microsecond=125000
    )
    assert bounds("2026-10-17T14:30-05:00", None, "UTC", NOW)[0] == NOW.replace(hour=19, minute=30)


@pytest.mark.parametrize(
    "value",
    ["9:05", "09:5", "2026-1-07", "2026-10-7", "2026-10-17T9:05", "14:30-5:00", "14:30-05:60", "14:30+24:00"],
)
def test_bad_padding_and_offsets_have_actionable_hint(value):
    with pytest.raises(ValueError) as error:
        bounds(value, None, "America/Chicago", NOW)
    message = str(error.value)
    assert "Leading zeros" in message and "UTC timezone offset" in message and "America/Chicago" in message
    assert "14:30-05:00" in message and "today" in message


def test_time_only_preserves_clock_change_and_range_guards():
    fold = datetime(2026, 11, 1, 12, tzinfo=UTC)
    gap = datetime(2026, 3, 8, 12, tzinfo=UTC)
    for now, value in [(fold, "01:30"), (gap, "02:30")]:
        with pytest.raises(ValueError, match="clock change"):
            bounds(value, None, "America/Chicago", now)
    start, end = bounds("01:30-05:00", "01:30-06:00", "America/Chicago", fold)
    assert end - start == timedelta(hours=1)
    for since, until in [("16:00", "15:00"), ("14:30", "14:30"), (None, "23:59")]:
        with pytest.raises(ValueError, match="past time range"):
            bounds(since, until, "America/Chicago", NOW)


def test_quote_command_returns_timestamp_guidance_without_reading_history(tmp_path):
    async def run():
        cfg = configured()
        store = Store(tmp_path / "statistics.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        listener = DiscordListener(cfg.bots[0], cfg, store, pipeline)
        replies = []

        async def send(text, **kwargs):
            replies.append(text)

        interaction = SimpleNamespace(
            guild_id=1,
            response=SimpleNamespace(is_done=lambda: True),
            followup=SimpleNamespace(send=send),
        )
        await listener.commands.get_command("quotes").callback(interaction, Mock(), "9:5", None)
        assert len(replies) == 1 and "Leading zeros" in replies[0] and "UTC timezone offset" in replies[0]
        await listener.close()
        await pipeline.close()
        store.close()

    asyncio.run(run())


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
