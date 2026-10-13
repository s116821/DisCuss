from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from discuss.calendar import window_at
from discuss.discord_adapter import DiscordListener
from discuss.lexicon import Lexicon
from discuss.reporting import Rank, Standings, render, report_members, resolve_page_names
from discuss.speech import SpeechPipeline
from discuss.storage import Store
from test_detection_reporting import configured


def window():
    return window_at(datetime(2026, 10, 13, 23, tzinfo=UTC), "America/Chicago", "week")


def test_readable_summary_omits_words_and_ids_and_preserves_rates():
    member = "251951339196645377"
    board = Standings((Rank(member, 21, 1800, 42),), (Rank(member, 21, 1800, 42),), {member: {"private-word": 21}})
    text = "\n".join(render(window(), board, member_name=lambda m: "PinkFootedPeepee", timezone="America/Chicago"))
    assert "**Weekly standings**" in text and "Oct 12–18, 2026" in text
    assert "**PinkFootedPeepee**" in text and "**21**" in text and "**42.00/hr**" in text
    assert "30.0m monitored" in text
    assert member not in text and "private-word" not in text and "Per-word" not in text


def test_reserved_pages_resolve_without_storing_names_or_changing_boundaries():
    from discuss.detection_reporting import units

    ranks = tuple(Rank(str(251951339196645377 + i), i + 1, 1800, (i + 1) * 2) for i in range(40))
    board = Standings(ranks, ranks, {})
    pages = render(window(), board, reserve_names=True, timezone="America/Chicago", limit=512)
    resolved = [resolve_page_names(page, lambda m: "😀" * 100 + "@everyone", limit=512) for page in pages]
    assert len(resolved) == len(pages) and len(resolved) > 1
    assert all(units(page) <= 512 and "{{member:" not in page and "@everyone" not in page for page in resolved)
    assert sum(page.count("** · **") for page in resolved) == 80
    assert all("**Total cusses**" in page or "**Cusses per monitored hour**" in page for page in resolved)
    assert all("😀" not in page for page in pages)
    assert "Unknown member" in resolve_page_names(pages[0], lambda m: "Unknown member")


def test_legacy_pages_remove_word_rows_and_resolve_identity_once():
    page = (
        "DisCuss week\nTotal standings\n1. Member 251951339196645377: 2 detected\n"
        "Per-word counts\nMember 251951339196645377: violet = 2"
    )
    result = resolve_page_names(page, lambda m: "Member 123")
    assert "Member 123: 2 detected" in result
    assert "251951339196645377" not in result and "violet" not in result and "Per-word" not in result
    dense = "\n".join(f"{i}. Member 251951339196645377: 2 detected" for i in range(1, 36))
    from discuss.detection_reporting import units

    shortened = resolve_page_names(dense, lambda m: "😀" * 100 + "@everyone")
    assert units(shortened) <= 1900 and shortened.count("2 detected") == 35
    assert "251951339196645377" not in shortened


def test_named_standings_required_member_words_and_safe_status(tmp_path):
    async def run():
        cfg = configured()
        cfg.servers[0].leaderboards.timezone = "America/Chicago"
        store = Store(tmp_path / "statistics.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        listener = DiscordListener(cfg.bots[0], cfg, store, pipeline)
        server = SimpleNamespace(
            name="Fun Server",
            get_member=lambda m: SimpleNamespace(display_name="Pink" if m == 100 else "Buddy"),
            get_channel=lambda c: SimpleNamespace(name="Voice Lounge"),
        )
        listener.client.get_guild = Mock(return_value=server)
        listener.client.get_user = Mock(return_value=None)
        now = datetime.now(UTC)
        store.ingest("1", "100", "10", "a", now, "violet violet", Lexicon(False, ["violet"]))
        store.ingest("1", "200", "10", "b", now, "shade", Lexicon(False, ["shade"]))
        replies = []

        async def send(text, **kwargs):
            replies.append(text)
            assert kwargs["ephemeral"] and not kwargs["allowed_mentions"].users

        interaction = SimpleNamespace(
            guild_id=1,
            user=SimpleNamespace(id=100),
            permissions=SimpleNamespace(administrator=True),
            response=SimpleNamespace(is_done=lambda: True),
            followup=SimpleNamespace(send=send),
        )
        await listener.commands.get_command("standings").callback(interaction, "week")
        assert "Pink" in " ".join(replies) and "Buddy" in " ".join(replies)
        assert "violet" not in " ".join(replies) and "Member 100" not in " ".join(replies)
        words = listener.commands.get_command("words")
        assert next(p for p in words.parameters if p.name == "member").required
        replies.clear()
        await words.callback(interaction, SimpleNamespace(id=100, display_name="Pink"), "week")
        assert "Pink — word counts" in replies[0] and "violet" in replies[0] and "shade" not in replies[0]
        listener.coordinator = SimpleNamespace(
            listeners={
                "primary": SimpleNamespace(
                    client=SimpleNamespace(user=SimpleNamespace(display_name="Cuss Bot")),
                    current_channel=lambda s: "10",
                    connected=lambda s: True,
                    capture_ready=lambda s: True,
                )
            },
            errors={},
        )
        replies.clear()
        await listener.commands.get_command("status").callback(interaction)
        assert "Fun Server" in replies[0] and "#Voice Lounge" in replies[0] and "Cuss Bot" in replies[0]
        assert "channel=10" not in replies[0] and "Server 1" not in replies[0]
        assert listener.channel_name("1", None) == "Not connected"
        await listener.close()
        await pipeline.close()
        store.close()

    asyncio.run(run())


def test_scheduled_publish_resolves_rest_fallback_without_mentions(tmp_path):
    async def run():
        cfg = configured()
        store = Store(tmp_path / "statistics.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        listener = DiscordListener(cfg.bots[0], cfg, store, pipeline)
        channel = Mock(spec=discord.TextChannel)
        channel.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True)
        channel.send = AsyncMock(return_value=SimpleNamespace(id=123))
        server = SimpleNamespace(me=object(), get_member=lambda m: None, get_channel=lambda c: channel)
        listener.client.get_guild = Mock(return_value=server)
        listener.client.get_user = Mock(return_value=None)
        listener.client.fetch_user = AsyncMock(return_value=SimpleNamespace(display_name="Stark @everyone"))
        board = Standings((Rank("100", 2, 3600, 2),), (), {"100": {"violet": 2}})
        page = render(window(), board, reserve_names=True)[0]
        assert report_members(page) == {"100"}
        await listener.publish(cfg.servers[0], page, "week", 0)
        text = channel.send.call_args.args[0]
        assert "Stark ＠everyone" in text and "{{member:" not in text and "violet" not in text
        assert not channel.send.call_args.kwargs["allowed_mentions"].users
        assert channel.send.call_args.kwargs["suppress_embeds"]
        await listener.publish(cfg.servers[0], page, "week", 0)
        assert listener.client.fetch_user.await_count == 1
        listener.client.fetch_user.side_effect = TimeoutError
        missing = render(window(), Standings((Rank("200", 2, 3600, 2),), (), {}), reserve_names=True)[0]
        await listener.publish(cfg.servers[0], missing, "week", 1)
        assert "Unknown member" in channel.send.call_args.args[0]
        assert "{{member:" not in channel.send.call_args.args[0]
        await listener.publish(cfg.servers[0], missing, "week", 1)
        assert listener.client.fetch_user.await_count == 2
        await listener.close()
        await pipeline.close()
        store.close()

    asyncio.run(run())
