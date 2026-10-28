from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from discuss.config import Playback, validate_config
from discuss.lexicon import Lexicon
from discuss.playback import PlaybackController, Target
from discuss.speech import SpeechChunk, SpeechWord
from test_config_policy import config_data

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)
TARGET = Target("primary", "10", "100")


def policy(**settings):
    data = config_data()
    data["servers"][0]["playback"] = {"enabled": True, **settings}
    data["servers"][0]["profanity"] = {"use_builtin_list": False, "custom_words": ["violet"]}
    return validate_config(json.dumps(data)).servers[0]


def controller(draw=lambda: 0.0):
    replay = PlaybackController(lambda s, m: True, draw)
    replay.clock = lambda: NOW + timedelta(seconds=1)
    return replay


def capture(replay, server, *, at=NOW, member="100", channel="10"):
    chunk = SpeechChunk("1", channel, member, "synthetic", at, b"\x01\x00" * (48000 * 2 * 12))
    words = [SpeechWord("violet", 0.3, 0.9, 0.7)]
    replay.offer(server, chunk, words, Lexicon(False, ["violet"]).matches("violet"))


def test_defaults_and_interval_validation():
    assert not Playback().enabled and Playback().interval_seconds == 900
    assert Playback().mode == "random"
    assert Playback(mode="cadence", interval_seconds=5).cadence_timing
    with pytest.raises(ValueError):
        Playback(interval_seconds=0)


@pytest.mark.parametrize("mode", ["random", "first_curse"])
@pytest.mark.parametrize("interval", [5, 30, 60, 119, 119.9])
def test_randomized_modes_reject_intervals_below_two_minutes(mode, interval):
    with pytest.raises(ValueError, match="interval_seconds >= 120"):
        Playback(mode=mode, interval_seconds=interval)
    normal = Playback(mode=mode, interval_seconds=120)
    assert normal.mode == mode and not normal.cadence_timing


@pytest.mark.parametrize("draw,member", [(0.0, "100"), (0.8, "200"), (0.99, "300")])
def test_weighted_current_participants(draw, member):
    server = policy()
    server.head_hunt.priority_member_ids = ["100", "200"]
    server.head_hunt.maximum_weight, server.head_hunt.minimum_weight, server.head_hunt.default_weight = 10, 2, 1
    replay = controller(lambda: draw)
    replay.tick(server, NOW, [TARGET, Target("primary", "10", "200"), Target("primary", "10", "300")])
    assert replay.cycles["1"].target.member == member


def test_random_listening_playback_window_and_bounded_clip():
    values = iter([0.0, 0.5, 0.5])
    replay, server = controller(lambda: next(values)), policy()
    replay.tick(server, NOW, [TARGET])
    cycle = replay.cycles["1"]
    assert NOW < cycle.listen_at < cycle.end
    capture(replay, server)  # Speech before randomized capture start cannot be saved.
    assert cycle.clip is None
    replay.clock = lambda: NOW + timedelta(seconds=460)
    capture(replay, server, at=NOW + timedelta(seconds=455))
    assert cycle.clip and len(cycle.clip) <= 8 * 192000
    assert replay.clock() <= cycle.play_at < cycle.end
    assert "\\x01" not in repr(cycle)
    calls = []
    replay.start = lambda s, t, p, done: calls.append((s, t, len(p))) or True
    replay.tick(server, cycle.play_at, [TARGET])
    replay.tick(server, cycle.play_at + timedelta(seconds=1), [TARGET])
    assert len(calls) == 1 and cycle.clip is None and replay.played == 1


def test_cadence_and_no_capture_noop():
    replay, server = controller(), policy(mode="cadence", interval_seconds=30)
    calls = []
    replay.start = lambda s, t, p, done: calls.append(len(p)) or True
    replay.tick(server, NOW, [TARGET])
    capture(replay, server)
    replay.tick(server, NOW + timedelta(seconds=29), [TARGET])
    assert not calls
    replay.tick(server, NOW + timedelta(seconds=30), [TARGET])
    assert len(calls) == 1
    replay.tick(server, NOW + timedelta(seconds=60), [TARGET])
    assert len(calls) == 1 and replay.skipped == 1


def test_random_replay_waits_for_delayed_capture_before_selecting_remaining_time():
    values = iter([0.0, 0.1, 0.5])
    replay, server = controller(lambda: next(values)), policy()
    calls = []
    replay.start = lambda s, t, pcm, done: calls.append(t) or True
    replay.tick(server, NOW, [TARGET])
    cycle = replay.cycles["1"]
    # Listening has started, but acquisition/recognition is deliberately delayed.
    replay.tick(server, NOW + timedelta(seconds=739), [TARGET])
    assert cycle.clip is None and cycle.play_at is None and not calls
    acquired = NOW + timedelta(seconds=740)
    replay.clock = lambda: acquired
    capture(replay, server, at=NOW + timedelta(seconds=700))
    assert cycle.clip and acquired < cycle.play_at < cycle.end
    assert cycle.play_at + timedelta(seconds=len(cycle.clip) / 192000) <= cycle.end
    replay.tick(server, acquired, [TARGET])
    assert not calls
    replay.tick(server, cycle.play_at, [TARGET])
    assert calls == [TARGET]


@pytest.mark.parametrize("change", ["member", "channel", "disabled", "opt_out"])
def test_selection_cancels_before_capture_but_captured_clip_survives(change):
    for captured in (False, True):
        replay, server = controller(), policy(mode="cadence", interval_seconds=30)
        replay.tick(server, NOW, [TARGET])
        if captured:
            capture(replay, server)
        if change == "member":
            replay.tick(server, replay.clock(), [])
        elif change == "channel":
            replay.tick(server, replay.clock(), [Target("primary", "20", "100")])
        elif change == "disabled":
            server.monitoring_enabled = False
            replay.tick(server, replay.clock(), [TARGET])
        else:
            replay.allowed = lambda s, m: False
            replay.discard("1", "100")
        if captured:
            assert replay.cycles["1"].clip
            calls = []
            replay.start = lambda s, t, p, done: calls.append(t) or True
            replay.tick(server, NOW + timedelta(seconds=30), [])
            assert calls == [TARGET]
            replay.discard("1", "100")
            assert replay.active
            replay.discard("1", force=True)
            assert not replay.active and not replay.cycles
        else:
            assert all(c.target is None for c in replay.cycles.values())


def test_other_members_late_chunks_and_offline_start_cannot_supply_clip():
    replay, server = controller(), policy()
    replay.tick(server, NOW, [])
    assert not replay.cycles
    replay.tick(server, NOW, [TARGET])
    capture(replay, server, member="200")
    capture(replay, server, channel="20")
    assert replay.cycles["1"].clip is None
    replay.clock = lambda: NOW + timedelta(seconds=901)
    capture(replay, server)
    assert replay.cycles["1"].clip is None
    replay.tick(server, replay.clock(), [TARGET])
    assert replay.cycles["1"].end == NOW + timedelta(seconds=1800)


@pytest.mark.parametrize("mode", ["cadence", "first_curse"])
def test_pipeline_to_memory_playback_after_member_leaves_or_opts_out(tmp_path, mode):
    import asyncio

    from discuss.coordinator import Coordinator
    from discuss.detection_reporting import notice
    from discuss.discord_adapter import MemoryAudio
    from discuss.speech import SpeechPipeline
    from discuss.storage import Store
    from test_runtime import Transcriber, Worker, presence

    async def run():
        data = config_data()
        data["servers"][0]["playback"] = {
            "enabled": True,
            "mode": mode,
            "interval_seconds": 5 if mode == "cadence" else 120,
        }
        cfg = validate_config(json.dumps(data))
        server = cfg.servers[0]
        server.profanity.use_builtin_list = False
        server.profanity.custom_words = ["violet"]
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Transcriber())
        pipeline.playback.clock = lambda: NOW + timedelta(seconds=1)
        pipeline.playback.draw = lambda: 0
        pipeline.start()

        class PlaybackWorker(Worker):
            def play_clip(self, server_id, target, pcm, done):
                assert self.current_channel(server_id) == target.channel
                source = MemoryAudio(pcm)
                result = bytearray()
                while frame := source.read():
                    assert len(frame) == 3840
                    result.extend(frame)
                source.cleanup()
                assert not source.pcm
                self.published.append(len(result))
                done()
                return True

            def stop_clip(self, server_id):
                pass

        worker = PlaybackWorker("primary", {"1": [presence("10", "100")]})
        coordinator = Coordinator(cfg, store, pipeline, {"primary": worker}, draw=lambda: 0, clock=lambda: NOW)
        await coordinator.tick(NOW, 0)
        assert pipeline.submit(SpeechChunk("1", "10", "100", "clip", NOW, b"\x01\x00" * 192000))
        for _ in range(100):
            if pipeline.processed:
                break
            await asyncio.sleep(0.01)
        assert pipeline.playback.cycles["1"].clip
        store.set_opt_out("1", "100", True, NOW + timedelta(seconds=2))
        pipeline.discard("1", "100")
        worker.occupants["1"] = [presence("10")]
        await coordinator.report_tick(NOW + timedelta(seconds=5), 5)
        assert worker.published and pipeline.playback.played == 1
        assert "after opt-out" in notice(server)
        assert "audio/transcripts are discarded" not in notice(server)
        assert b"\x01\x00" * 1000 not in (tmp_path / "stats.sqlite3").read_bytes()
        await coordinator.close(NOW + timedelta(seconds=6))
        store.close()

    asyncio.run(run())


def test_first_curse_random_window_first_acquired_wins_and_routes_secondary_listener():
    values = iter([0.5, 0.5])  # Only listen-start and post-acquisition playback draws; no speaker draw.
    replay, server = controller(lambda: next(values)), policy(mode="first_curse", interval_seconds=600)
    other = Target("secondary", "20", "200")
    server.head_hunt.priority_member_ids = ["100"]
    server.head_hunt.default_weight = 0  # Weights do not exclude first-curse candidates.
    replay.tick(server, NOW, [TARGET, other])
    cycle = replay.cycles["1"]
    assert cycle.target is None and NOW < cycle.listen_at < cycle.end
    capture(replay, server, member="200", channel="20")  # Before listening begins.
    assert cycle.clip is None and cycle.target is None and cycle.play_at is None
    acquired = NOW + timedelta(seconds=450)
    replay.clock = lambda: acquired
    capture(replay, server, at=NOW + timedelta(seconds=400), member="200", channel="20")
    saved = cycle.clip
    assert saved and len(saved) <= 8 * 192000 and cycle.target == other
    assert not cycle.candidates and acquired < cycle.play_at < cycle.end
    assert cycle.play_at + timedelta(seconds=len(saved) / 192000) <= cycle.end
    capture(replay, server, at=NOW + timedelta(seconds=350))  # Older speech, recognized later, cannot replace it.
    assert cycle.target == other and cycle.clip is saved
    calls = []
    replay.start = lambda s, t, pcm, done: calls.append((t, pcm)) or True
    replay.tick(server, acquired, [TARGET, other])
    assert not calls
    replay.tick(server, cycle.play_at, [TARGET])  # Captured clip survives departure.
    replay.tick(server, cycle.play_at + timedelta(seconds=1), [TARGET])
    assert calls == [(other, saved)] and replay.played == 1 and cycle.clip is None


@pytest.mark.parametrize("change", ["opt_out", "departure", "channel", "exclusion"])
def test_first_curse_candidate_changes_do_not_cancel_other_speakers(change):
    replay, server = controller(), policy(mode="first_curse")
    other = Target("primary", "10", "200")
    replay.tick(server, NOW, [TARGET, other])
    if change == "opt_out":
        replay.allowed = lambda s, m: m != "100"
        replay.discard("1", "100")
    elif change == "exclusion":
        replay.allowed = lambda s, m: m != "100"
    else:
        targets = [other] if change == "departure" else [Target("primary", "20", "100"), other]
        replay.tick(server, replay.clock(), targets)
    cycle = replay.cycles["1"]
    capture(replay, server)
    assert not cycle.captured and not cycle.consumed
    capture(replay, server, member="200")
    assert cycle.captured and cycle.target == other


def test_first_curse_only_current_assignments_can_supply_and_new_arrivals_are_eligible():
    replay, server = controller(), policy(mode="first_curse")
    replay.tick(server, NOW, [TARGET])
    capture(replay, server, member="200")
    capture(replay, server, channel="20")
    assert replay.cycles["1"].clip is None
    replay.tick(server, replay.clock(), [])
    capture(replay, server)  # All participants departed; no stale eligibility.
    assert replay.cycles["1"].clip is None
    arrival = Target("secondary", "20", "200")
    replay.tick(server, replay.clock(), [arrival])
    capture(replay, server, member="200", channel="10")
    assert replay.cycles["1"].clip is None
    capture(replay, server, member="200", channel="20")
    assert replay.cycles["1"].target == arrival


@pytest.mark.parametrize("setting", ["monitoring_enabled", "playback"])
def test_first_curse_disabled_before_capture_rejects_offers(setting):
    replay, server = controller(), policy(mode="first_curse")
    replay.tick(server, NOW, [TARGET])
    if setting == "playback":
        server.playback.enabled = False
    else:
        server.monitoring_enabled = False
    capture(replay, server)
    assert replay.cycles["1"].clip is None
    replay.tick(server, replay.clock(), [TARGET])
    assert not replay.cycles


def test_first_curse_expiry_at_minimum_randomized_interval():
    replay, server = controller(), policy(mode="first_curse", interval_seconds=120)
    other = Target("primary", "10", "200")
    replay.tick(server, NOW, [TARGET, other])
    cycle = replay.cycles["1"]
    assert cycle.listen_at == NOW and cycle.target is None
    capture(replay, server, member="200")
    assert cycle.play_at == NOW + timedelta(seconds=1)
    calls = []
    replay.start = lambda s, t, pcm, done: calls.append(t) or done() or True
    replay.tick(server, NOW, [TARGET, other])
    assert not calls
    replay.tick(server, NOW + timedelta(seconds=1), [TARGET, other])
    assert calls == [other]
    replay.tick(server, NOW + timedelta(seconds=120), [TARGET, other])
    replay.clock = lambda: NOW + timedelta(seconds=241)
    capture(replay, server, at=NOW + timedelta(seconds=130))
    assert replay.cycles["1"].clip is None
    replay.tick(server, replay.clock(), [TARGET, other])
    capture(replay, server, at=NOW + timedelta(seconds=130))  # Previous cycle speech cannot enter the next.
    assert replay.cycles["1"].clip is None and replay.skipped == 1 and calls == [other]


def test_first_curse_coordinator_handoff_preserves_other_listener_opportunity(tmp_path):
    import asyncio

    from discuss.coordinator import Coordinator
    from discuss.speech import SpeechPipeline
    from discuss.storage import Store
    from test_runtime import Transcriber, Worker, presence

    async def run():
        data = config_data()
        data["bots"].append({"name": "secondary", "token": "offline-secondary-" + "x" * 64})
        data["servers"][0].update(
            mode="fixed_channels",
            assignments=[{"bot": "primary", "channel_id": "10"}, {"bot": "secondary", "channel_id": "20"}],
            playback={"enabled": True, "mode": "first_curse"},
        )
        cfg = validate_config(json.dumps(data))
        server = cfg.servers[0]
        server.profanity.use_builtin_list = False
        server.profanity.custom_words = ["violet"]
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Transcriber())
        pipeline.playback.clock = lambda: NOW + timedelta(seconds=1)
        pipeline.playback.draw = lambda: 0
        pipeline.start()
        primary = Worker("primary", {"1": [presence("10", "100")]})
        secondary = Worker("secondary", {"1": [presence("20", "200")]})
        workers = {"primary": primary, "secondary": secondary}
        coordinator = Coordinator(cfg, store, pipeline, workers, draw=lambda: 0, clock=lambda: NOW)
        await coordinator.tick(NOW, 0)
        cycle = pipeline.playback.cycles["1"]
        assert set(cycle.candidates) == {TARGET, Target("secondary", "20", "200")}
        primary.occupants["1"] = [presence("10")]
        await coordinator.tick(NOW + timedelta(seconds=1), 1)
        assert pipeline.playback.cycles["1"] is cycle
        assert cycle.candidates == (Target("secondary", "20", "200"),)
        capture(pipeline.playback, server)  # Stale released-listener speech is rejected.
        assert cycle.clip is None
        assert pipeline.submit(SpeechChunk("1", "20", "200", "clip", NOW, b"\x01\x00" * 192000))
        for _ in range(100):
            if pipeline.processed:
                break
            await asyncio.sleep(0.01)
        assert cycle.clip and cycle.target == Target("secondary", "20", "200")
        await coordinator.close(NOW + timedelta(seconds=2))
        assert not pipeline.playback.cycles
        store.close()

    asyncio.run(run())
