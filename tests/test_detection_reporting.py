from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from discuss.config import ConfigError, validate_config
from discuss.coordinator import Coordinator
from discuss.detection_reporting import HEADER, DetectionFeed, instances, notice, render, units
from discuss.discord_adapter import DiscordListener
from discuss.lexicon import Lexicon
from discuss.speech import SpeechChunk, SpeechPipeline, SpeechWord
from discuss.storage import Store
from test_config_policy import config_data
from test_runtime import Worker, moment


def configured(*, interval: float = 0):
    data = config_data()
    server = data["servers"][0]
    server["privacy"]["context_reporting_acknowledged"] = True
    server["detection_reporting"] = {"enabled": True, "interval_seconds": interval}
    return validate_config(json.dumps(data))


def clocked_feed(tmp_path: Path, *, interval: float = 0):
    config = configured(interval=interval)
    store = Store(tmp_path / "statistics.sqlite3")
    clock = [0.0]
    feed = DetectionFeed(config, store, lambda s, m: not store.opted_out(s, m) and not store.disabled(s))
    feed.monotonic = lambda: clock[0]
    return config, store, clock, feed


def add(store, feed, chunk: str, *, member: str = "100", text: str = "One VIOLET! Then shade here."):
    lexicon = Lexicon(False, ["violet", "shade"])
    at = datetime(2026, 10, 13, 22, 26, tzinfo=UTC)
    matches = lexicon.matches(text)
    times = [at + timedelta(seconds=i) for i in range(len(matches))]
    if store.ingest("1", member, "10", chunk, at, text, lexicon, detection_times=times):
        feed.offer("1", "10", member, chunk, text, matches, times)


def test_configuration_defaults_acknowledgement_and_bounds() -> None:
    original = validate_config(json.dumps(config_data())).servers[0]
    assert not original.detection_reporting.enabled
    assert original.detection_reporting.channel_id is None
    assert original.detection_reporting.context_words_per_side == 3
    data = config_data()
    data["servers"][0]["detection_reporting"] = {"enabled": True}
    with pytest.raises(ConfigError, match="excerpt"):
        validate_config(json.dumps(data))
    for settings in (
        {"context_words_per_side": -1},
        {"context_words_per_side": 21},
        {"interval_seconds": 400, "max_pending_age_seconds": 300},
        {"max_pending_bytes": 0},
    ):
        data["servers"][0]["detection_reporting"] = settings
        with pytest.raises(ConfigError):
            validate_config(json.dumps(data))


def test_context_grouping_original_case_punctuation_unicode_and_timezone() -> None:
    text = "One ＶＩＯＬＥＴ! Then shade here."
    lexicon = Lexicon(False, ["violet", "shade"])
    matches = lexicon.matches(text)
    times = [datetime(2026, 10, 13, 22, 26, tzinfo=UTC)] * 2
    group = instances("1", "10", "100", "a", text, matches, times, 3, 0)
    assert len(group) == 1 and group[0].count == 2
    assert group[0].quote == "One **ＶＩＯＬＥＴ**! Then **shade** here."
    server = configured().servers[0]
    server.leaderboards.timezone = "America/Chicago"
    line = render(group[0], "Stark", server)
    assert line == f"“{group[0].quote}” — [Stark](https://discord.com/users/100), October 13, 2026 @ 5:26 pm CDT"
    assert "(100)" not in line
    assert "cusses" not in line and "[server" not in line and " / channel" not in line
    assert group[0].quote not in repr(group[0])
    # Same lexicon behavior for composing characters and expanding compatibility tokens.
    for raw, word in (("cafe\u0301!", "café"), ("ﬃ!", "ffi"), ("İ!", "i")):
        lexicon = Lexicon(False, [word])
        ms = lexicon.matches(raw)
        assert instances("1", "10", "100", "a", raw, ms, times[: len(ms)], 0, 0)[0].count == 1
    compatibility = "℀!"
    ms = Lexicon(False, ["a", "c"]).matches(compatibility)
    group = instances("1", "10", "100", "a", compatibility, ms, times, 3, 0)[0]
    assert group.count == 2 and group.quote == "**℀**!"


def test_nonoverlapping_windows_and_zero_context_remain_separate() -> None:
    text = "violet a b c d e f shade end"
    matches = Lexicon(False, ["violet", "shade"]).matches(text)
    groups = instances("1", "10", "100", "a", text, matches, [moment()] * 2, 3, 0)
    assert len(groups) == 2 and sum(i.count for i in groups) == 2
    assert len(instances("1", "10", "100", "a", text, matches, [moment()] * 2, 0, 0)) == 2


def test_immediate_digest_speaker_separation_and_idempotence(tmp_path: Path) -> None:
    async def run() -> None:
        config, store, _, feed = clocked_feed(tmp_path)
        pages = []

        async def send(server, page):
            pages.append(page)
            return "receipt"

        feed.bind(send, lambda s, m: "Stark" if m == "100" else "Other", lambda s: True)
        add(store, feed, "a")
        add(store, feed, "b", member="200")
        await asyncio.sleep(0.02)
        assert len(pages) == 1 and pages[0].count(" — ") == 2
        assert pages[0].startswith("“") and "Detected speech" not in pages[0]
        assert (
            " — [Stark](https://discord.com/users/100)," in pages[0]
            and " — [Other](https://discord.com/users/200)," in pages[0]
        )
        add(store, feed, "a")
        feed.tick()
        await asyncio.sleep(0)
        assert len(pages) == 1 and not feed.pending
        assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 4
        assert config.servers[0].detection_reporting.channel_id is None
        await feed.close()
        store.close()

    asyncio.run(run())


def test_interval_empty_windows_and_bounded_queue(tmp_path: Path) -> None:
    async def run() -> None:
        config, store, clock, feed = clocked_feed(tmp_path, interval=60)
        config.servers[0].detection_reporting.max_pending_instances = 2
        pages = []

        async def send(server, page):
            pages.append(page)
            return "receipt"

        feed.bind(send, lambda s, m: "Member", lambda s: True)
        for chunk in ("a", "b", "c"):
            add(store, feed, chunk)
        await asyncio.sleep(0)
        assert not pages and len(feed.pending) == 2 and feed.dropped == 1
        clock[0] = 59
        feed.tick()
        assert not pages
        clock[0] = 60
        feed.tick()
        await asyncio.sleep(0.02)
        assert len(pages) == 1 and pages[0].count(" — [Member](https://discord.com/users/") == 2
        clock[0] = 120
        feed.tick()
        await asyncio.sleep(0)
        assert len(pages) == 1
        await feed.close()
        store.close()

    asyncio.run(run())


def test_pagination_partial_retry_and_no_local_quote_storage(tmp_path: Path) -> None:
    async def run() -> None:
        _, store, clock, feed = clocked_feed(tmp_path, interval=60)
        pages, attempts = [], []
        failed = [False]

        async def send(server, page):
            attempts.append(page)
            if len(pages) == 1 and not failed[0]:
                failed[0] = True
                raise OSError("Synthetic outbound failure")
            pages.append(page)
            return str(len(pages))

        feed.bind(send, lambda s, m: "Member-" + m, lambda s: True)
        for number in range(40):
            add(store, feed, str(number), member=str(100 + number), text="UNRELATEDMARKER violet **@everyone**")
        clock[0] = 60
        feed.tick()
        await asyncio.wait_for(feed.tasks["1"], 2)
        assert len(pages) == 1 and feed.failures == 1 and feed.pending
        clock[0] = 70
        feed.tick()
        await asyncio.wait_for(feed.tasks["1"], 2)
        assert len(pages) > 1 and all(units(page) <= 1900 for page in pages)
        assert sum(page.count(" — [Member-") for page in pages) == 40
        assert attempts.count(pages[0]) == 1 and not feed.pending
        assert all("@everyone" not in p for p in pages)
        assert "UNRELATEDMARKER" not in " ".join(store.db.iterdump())
        backup = tmp_path / "backup.sqlite3"
        store.backup(backup)
        assert b"UNRELATEDMARKER" not in backup.read_bytes()
        await feed.close()
        store.close()

    asyncio.run(run())


def test_expiry_backing_deletion_and_shutdown_discard(tmp_path: Path) -> None:
    async def run() -> None:
        config, store, clock, feed = clocked_feed(tmp_path, interval=60)
        add(store, feed, "a")
        store.delete_member("1", "100")
        feed.tick()
        assert not feed.pending
        add(store, feed, "b")
        clock[0] = config.servers[0].detection_reporting.max_pending_age_seconds
        feed.tick()
        assert not feed.pending and feed.expired == 1
        add(store, feed, "c")
        assert feed.pending
        await feed.close()
        assert not feed.pending and not feed.tasks
        store.close()

    asyncio.run(run())


def test_optout_cancels_inflight_without_reviving_on_optin(tmp_path: Path) -> None:
    async def run() -> None:
        _, store, _, feed = clocked_feed(tmp_path)
        entered, never = asyncio.Event(), asyncio.Event()
        sent = []

        async def send(server, page):
            entered.set()
            await never.wait()
            sent.append(page)
            return "receipt"

        feed.bind(send, lambda s, m: "Member", lambda s: True)
        add(store, feed, "a")
        await entered.wait()
        store.set_opt_out("1", "100", True, moment())
        feed.discard("1", "100")
        store.set_opt_out("1", "100", False, moment())
        await asyncio.sleep(0.02)
        assert not feed.pending and not sent and not feed.inflight
        await feed.close()
        store.close()

    asyncio.run(run())


def test_primary_channel_fallback_override_and_safe_sdk_arguments(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = configured()
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        listener = DiscordListener(cfg.bots[0], cfg, store, pipeline)
        channel = Mock(spec=discord.TextChannel)
        channel.name = "leaderboard-alerts"
        channel.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True)
        channel.send = AsyncMock(return_value=SimpleNamespace(id=789))
        server = Mock()
        server.me = SimpleNamespace(id=999)
        server.get_channel.return_value = channel
        listener.client.get_guild = Mock(return_value=server)
        policy = cfg.servers[0]
        await listener.notice(policy)
        assert "excerpts go to #leaderboard-alerts" in channel.send.call_args.args[0]
        await listener.publish_detections(policy, "Safe test")
        server.get_channel.assert_called_with(int(policy.report_channel_id))
        policy.detection_reporting.channel_id = "50"
        separate = Mock(spec=discord.TextChannel)
        separate.name = "separate-alerts"
        separate.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True)
        separate.send = AsyncMock(return_value=SimpleNamespace(id=790))
        server.get_channel.side_effect = lambda identifier: separate if identifier == 50 else channel
        await listener.publish_detections(policy, "Safe test")
        server.get_channel.assert_called_with(50)
        kwargs = separate.send.call_args.kwargs
        assert kwargs["suppress_embeds"] and not kwargs["allowed_mentions"].everyone
        assert not kwargs["allowed_mentions"].users and not kwargs["allowed_mentions"].roles
        await listener.notice(policy)
        assert "excerpts go to #separate-alerts" in channel.send.call_args.args[0]
        assert "configured reporting channel" in notice(policy) and "channel 50" not in notice(policy)
        assert "＠everyone" in notice(policy, "@everyone") and "@everyone" not in notice(policy, "@everyone")
        concise = notice(policy, "separate-alerts")
        assert "remain on Discord" not in concise and "opt_out or opt_in" in concise
        assert "\n" not in concise and len(concise) < 220 and "words each side" not in concise
        custom = policy.model_copy(deep=True)
        custom.privacy.listening_notice = "Custom server processing notice for this test."
        assert notice(custom, "separate-alerts").startswith(custom.privacy.listening_notice)
        separate.permissions_for.return_value.send_messages = False
        with pytest.raises(ValueError, match="permissions"):
            await listener.publish_detections(policy, "Safe test")
        await listener.close()
        await pipeline.close()
        store.close()

    asyncio.run(run())


def test_pipeline_new_counts_only_and_report_work_is_independent(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = configured()
        cfg.servers[0].profanity.use_builtin_list = False
        cfg.servers[0].profanity.custom_words = ["violet"]
        store = Store(tmp_path / "stats.sqlite3")

        class Backend:
            def transcribe(self, chunk):
                return [SpeechWord("violet", 0), SpeechWord("here", 1)]

        class Listener(Worker):
            def speaker_name(self, server, member):
                return "Stark"

            async def publish_detections(self, server, page):
                entered.set()
                await release.wait()
                pages.append(page)
                return "receipt"

        entered, release, pages = asyncio.Event(), asyncio.Event(), []
        pipeline = SpeechPipeline(cfg, store, Backend())
        worker = Listener("primary", {"1": []})
        coordinator = Coordinator(cfg, store, pipeline, {"primary": worker})
        pipeline.start()
        chunk = SpeechChunk("1", "10", "100", "a", moment(), bytes(38400))
        pipeline.submit(chunk)
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.wait_for(coordinator.report_tick(moment(), 0), 0.5)
        pipeline.submit(chunk)
        for _ in range(100):
            if pipeline.processed == 2:
                break
            await asyncio.sleep(0.001)
        assert pipeline.processed == 2 and store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
        assert len(pipeline.detection_feed.pending) == 1
        release.set()
        await asyncio.sleep(0.02)
        assert len(pages) == 1 and pages[0].startswith("“")
        await coordinator.close(moment())
        store.close()

    asyncio.run(run())


def test_dense_context_splits_without_losing_matches_or_exceeding_utf16() -> None:
    text = " ".join(["violet!"] * 500)
    matches = Lexicon(False, ["violet"]).matches(text)
    groups = instances("1", "10", "100", "dense", text, matches, [moment()] * 500, 3, 0)
    assert len(groups) > 1 and sum(i.count for i in groups) == 500
    assert sum(i.quote.count("**violet**") for i in groups) == 500
    server = configured().servers[0]
    for item in groups:
        assert units(HEADER) + 1 + units(render(item, "😀" * 100 + "@everyone", server)) <= 1900


def test_page_budget_drains_one_digest_and_defers_new_interval_items(tmp_path: Path) -> None:
    async def run() -> None:
        cfg, store, clock, feed = clocked_feed(tmp_path, interval=60)
        cfg.servers[0].detection_reporting.max_pages_per_flush = 1
        pages = []

        async def send(server, page):
            pages.append(page)
            return str(len(pages))

        feed.bind(send, lambda s, m: "Member-" + m, lambda s: True)
        for number in range(40):
            add(store, feed, str(number), member=str(100 + number))
        clock[0] = 60
        feed.tick()
        await asyncio.sleep(0.02)
        assert len(pages) == 1 and feed.pending
        clock[0] = 61
        add(store, feed, "new", member="999")
        for _ in range(10):
            feed.tick()
            await asyncio.sleep(0.01)
        assert sum(page.count(" — [Member-") for page in pages) == 40
        assert [i.member for i in feed.pending] == ["999"]
        clock[0] = 121
        feed.tick()
        await asyncio.sleep(0.02)
        assert "Member-999" in pages[-1] and not feed.pending
        await feed.close()
        store.close()

    asyncio.run(run())


def test_byte_limit_and_missing_publisher_do_not_affect_counts(tmp_path: Path) -> None:
    cfg, store, clock, feed = clocked_feed(tmp_path, interval=60)
    cfg.servers[0].detection_reporting.max_pending_bytes = 1024
    for number in range(10):
        add(store, feed, str(number))
    assert feed.pending_bytes <= 1024 and feed.dropped > 0
    clock[0] = 60
    feed.tick()  # no bound publisher: no network attempt and no counting failure
    assert feed.pending and not feed.tasks and feed.failures == 0
    assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 20
    store.close()


def test_service_reload_and_admin_disable_clear_pending_excerpts(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = configured(interval=60)
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())
        worker = Worker("primary", {"1": []})
        coordinator = Coordinator(cfg, store, pipeline, {"primary": worker})
        add(store, pipeline.detection_feed, "a")
        assert pipeline.detection_feed.pending
        updated = cfg.model_copy(deep=True)
        updated.servers[0].detection_reporting.channel_id = "50"
        await coordinator.reload(updated, moment())
        assert not pipeline.detection_feed.pending and pipeline.detection_feed.config is updated
        add(store, pipeline.detection_feed, "b")
        store.set_disabled("1", True)
        pipeline.discard("1")
        store.set_disabled("1", False)
        assert not pipeline.detection_feed.pending
        await coordinator.close(moment())
        store.close()

    asyncio.run(run())


def test_all_listeners_share_primary_feed_with_independent_servers(tmp_path: Path) -> None:
    async def run() -> None:
        data = json.loads(configured(interval=60).model_dump_json())
        data["bots"][0]["token"] = "offline-primary-" + "x" * 64
        data["bots"].append({"name": "secondary", "token": "offline-secondary-" + "y" * 64})
        data["servers"][0].update(
            mode="fixed_channels",
            assignments=[
                {"bot": "primary", "channel_id": "10"},
                {"bot": "secondary", "channel_id": "20"},
            ],
        )
        data["servers"].append(dict(data["servers"][0], server_id="2", primary_bot="secondary"))
        cfg = validate_config(json.dumps(data))
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Mock())

        class Publisher(Worker):
            def __init__(self, name):
                super().__init__(name, {"1": [], "2": []})
                self.quotes = []

            def speaker_name(self, server, member):
                return self.name + "-cached-name-" + member

            async def publish_detections(self, server, page):
                self.quotes.append((server.server_id, page))
                return "receipt"

        primary, secondary = Publisher("primary"), Publisher("secondary")
        coordinator = Coordinator(cfg, store, pipeline, {"primary": primary, "secondary": secondary})
        clock = [0.0]
        pipeline.detection_feed.monotonic = lambda: clock[0]
        lexicon = Lexicon(False, ["violet"])
        for server, channel, member in (("1", "10", "100"), ("1", "20", "200"), ("2", "20", "300")):
            store.ingest(server, member, channel, "a", moment(), "violet", lexicon)
            pipeline.detection_feed.offer(server, channel, member, "a", "violet", lexicon.matches("violet"), [moment()])
        clock[0] = 60
        await coordinator.report_tick(moment(), 0)
        await asyncio.sleep(0.02)
        assert len(primary.quotes) == len(secondary.quotes) == 1
        assert primary.quotes[0][0] == "1" and primary.quotes[0][1].count(" — [primary-cached-name-") == 2
        assert secondary.quotes[0][0] == "2" and "secondary-cached-name-300" in secondary.quotes[0][1]
        assert "secondary-cached-name-300" not in primary.quotes[0][1]
        await coordinator.close(moment())
        store.close()

    asyncio.run(run())
