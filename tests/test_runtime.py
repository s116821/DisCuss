from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from discuss.calendar import window_at
from discuss.config import ConfigError, Transcription, validate_config
from discuss.coordinator import Coordinator
from discuss.discord_adapter import DiscordListener, MemberSink
from discuss.lexicon import Lexicon
from discuss.models import digest, model_path, verify_model
from discuss.reporting import Scheduler
from discuss.speech import LocalTranscriber, Segmenter, SpeechChunk, SpeechPipeline, SpeechWord
from discuss.storage import Store
from test_config_policy import config_data


def config():
    return validate_config(json.dumps(config_data()))


def moment() -> datetime:
    return datetime(2026, 10, 12, 12, tzinfo=UTC)


def frame(member: int, now: datetime, *, channel: int = 10, silent: bool = False):
    pcm = (np.zeros(1920, dtype="<i2") if silent else np.full(1920, 1000, dtype="<i2")).tobytes()
    return SimpleNamespace(
        server_id=1,
        channel_id=channel,
        member_id=member,
        received_at=now,
        pcm=pcm,
        concealed=False,
        timestamp=int((now - moment()).total_seconds() * 48000) % 2**32,
    )


class Transcriber:
    def transcribe(self, chunk: SpeechChunk) -> list[SpeechWord]:
        return [SpeechWord("violet", 0.1)]


class Worker:
    def __init__(self, name: str, occupants: dict) -> None:
        self.name, self.occupants = name, occupants
        self.assigned = {}
        self.connected_flag = True
        self.fail = False
        self.notices = []
        self.published = []
        self.released = []
        self.sinks = {}

    def ready(self, server: str) -> bool:
        return server in self.occupants

    def channels(self, server: str):
        return self.occupants.get(server, [])

    def current_channel(self, server: str):
        return self.assigned.get(server)

    def connected(self, server: str) -> bool:
        return server in self.assigned and self.connected_flag

    def capture_ready(self, server: str) -> bool:
        return self.connected(server)

    async def assign(self, server: str, channel: str, sink) -> None:
        if self.fail:
            raise OSError("Synthetic fault")
        self.assigned[server] = channel
        self.sinks[server] = sink

    async def release(self, server: str) -> None:
        self.released.append(server)
        self.assigned.pop(server, None)
        sink = self.sinks.pop(server, None)
        if sink:
            await sink.close("released")

    async def notice(self, policy) -> None:
        self.notices.append(policy.server_id)

    async def publish(self, policy, page, period, index) -> str:
        self.published.append((policy.server_id, period, index))
        return str(len(self.published))

    async def reconfigure(self, config) -> None:
        pass

    async def close(self) -> None:
        for server in list(self.assigned):
            await self.release(server)


def presence(channel: str, *members: str):
    from discuss.policy import ChannelPresence, MemberPresence

    return ChannelPresence(channel, tuple(MemberPresence(m) for m in members))


def test_segmentation_silence_overlap_handoff_and_limits() -> None:
    chunks = []
    settings = Transcription(minimum_chunk_seconds=0.02, silence_seconds=0.1, max_chunk_seconds=0.2)
    segmenter = Segmenter(settings, lambda c: chunks.append(c) or True, lambda s, m: True)
    now = moment()
    segmenter.feed(frame(100, now, silent=True))
    assert not segmenter.buffers
    segmenter.feed(frame(100, now))
    segmenter.feed(frame(200, now))
    assert len(segmenter.buffers) == 2
    segmenter.feed(frame(100, now + timedelta(milliseconds=20), channel=20))
    assert chunks[0].member_id == "100" and chunks[0].channel_id == "10"
    segmenter.expire(now + timedelta(seconds=1))
    assert {(c.member_id, c.channel_id) for c in chunks} == {("100", "10"), ("100", "20"), ("200", "10")}
    assert not segmenter.buffers
    assert all(len(c.pcm) <= 192000 * settings.max_chunk_seconds for c in chunks)
    blocked = Segmenter(settings, lambda c: True, lambda s, m: False)
    blocked.feed(frame(100, now))
    assert not blocked.buffers


def test_missing_and_tampered_model_cache_is_setup_failure(tmp_path: Path) -> None:
    settings = Transcription()
    with pytest.raises(ConfigError, match="model"):
        verify_model(tmp_path, settings)
    root = model_path(tmp_path, settings)
    root.mkdir(parents=True)
    files = ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"]
    for name in files:
        (root / name).write_bytes(b"synthetic fixture")
    manifest = {
        "model_id": settings.model_id,
        "revision": settings.revision,
        "files": {name: digest(root / name) for name in files},
    }
    (root / "model.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_model(tmp_path, settings) == root
    (root / "model.bin").write_bytes(b"tampered")
    with pytest.raises(ConfigError):
        verify_model(tmp_path, settings)


def test_local_backend_uses_local_files_and_native_resampling(tmp_path: Path, monkeypatch) -> None:
    import faster_whisper

    calls = {}

    class Model:
        def __init__(self, path, **kwargs):
            calls["loading"] = kwargs

        def transcribe(self, audio, **kwargs):
            calls["samples"] = len(audio)
            return iter(
                [SimpleNamespace(words=[SimpleNamespace(word="violet", start=0.1, probability=0.9, end=0.5)])]
            ), None

    monkeypatch.setattr("discuss.speech.verify_model", lambda state, settings: tmp_path)
    monkeypatch.setattr(faster_whisper, "WhisperModel", Model)
    transcriber = LocalTranscriber(tmp_path, Transcription())
    chunk = SpeechChunk("1", "10", "100", "chunk", moment(), bytes(38400))
    assert transcriber.transcribe(chunk) == [SpeechWord("violet", 0.1, 0.9, 0.5)]
    assert calls["loading"]["local_files_only"] is True
    assert calls["samples"] == 3200


def test_inference_is_nonblocking_and_midnight_words_are_fenced(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = config()
        cfg.servers[0].profanity.use_builtin_list = False
        cfg.servers[0].profanity.custom_words = ["violet"]
        cfg.servers[0].leaderboards.reports.day = True
        db = Store(tmp_path / "state.sqlite3")
        entered, finish = threading.Event(), threading.Event()

        class Blocking:
            def transcribe(self, chunk):
                entered.set()
                assert finish.wait(2)
                return [SpeechWord("violet", 0.1), SpeechWord("violet", 1.1)]

        pipeline = SpeechPipeline(cfg, db, Blocking())
        pipeline.start()
        before = datetime(2026, 10, 12, 23, 59, 59, 500000, tzinfo=UTC)
        after = before + timedelta(seconds=2)
        pipeline.submit(SpeechChunk("1", "10", "100", "chunk", before, bytes(384000)))
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()  # event loop continued while native inference blocked
        assert Scheduler(db).queue_due(cfg.servers[0], pipeline.watermark(after)) == 0
        finish.set()
        for _ in range(100):
            if pipeline.processed:
                break
            await asyncio.sleep(0.001)
        assert pipeline.processed == 1
        first = window_at(before, "UTC", "day")
        second = window_at(after, "UTC", "day")
        assert db.counts("1", first.start, first.end) == {"100": {"violet": 1}}
        assert db.counts("1", second.start, second.end) == {"100": {"violet": 1}}
        assert Scheduler(db).queue_due(cfg.servers[0], pipeline.watermark(after)) == 1
        await pipeline.close()
        db.close()

    asyncio.run(run())


def test_bounded_queue_optout_and_cancelled_native_result(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = config()
        cfg.transcription.max_queue = 1
        cfg.servers[0].profanity = cfg.servers[0].profanity.model_copy(
            update={"use_builtin_list": False, "custom_words": ["violet"]}
        )
        db = Store(tmp_path / "state.sqlite3")
        entered, finish = threading.Event(), threading.Event()

        class Blocking:
            def transcribe(self, chunk):
                entered.set()
                assert finish.wait(2)
                return [SpeechWord("violet", 0)]

        pipeline = SpeechPipeline(cfg, db, Blocking())
        pipeline.start()
        chunk = SpeechChunk("1", "10", "100", "chunk", moment(), bytes(38400))
        assert pipeline.submit(chunk)
        assert not pipeline.submit(chunk) and not pipeline.ready
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        pipeline.discard("1", "100")
        # Even opting back in before inference ends must not revive discarded audio.
        db.set_opt_out("1", "100", False, moment())
        finish.set()
        await pipeline.close()
        assert db.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert not pipeline.queue and not pipeline.segmenters
        db.close()

    asyncio.run(run())


def test_head_hunt_timing_idle_fixed_reload_and_identity_recovery(tmp_path: Path) -> None:
    async def run() -> None:
        data = config_data()
        data["bots"].append({"name": "secondary", "token": "offline-secondary-" + "y" * 64})
        cfg = validate_config(json.dumps(data))
        db = Store(tmp_path / "state.sqlite3")
        pipeline = SpeechPipeline(cfg, db, Transcriber())
        pipeline.start()
        primary = Worker("primary", {"1": [presence("10", "100"), presence("20", "200")]})
        secondary = Worker("secondary", {"1": [presence("10", "100"), presence("20", "200")]})
        draws = iter([0.0, 0.99, 0.0])
        clock = [moment()]
        coordinator = Coordinator(cfg, db, pipeline, {"primary": primary, "secondary": secondary}, lambda: next(draws))
        coordinator.clock = lambda: clock[0]

        async def tick(now, monotonic):
            clock[0] = now
            await coordinator.tick(now, monotonic)

        start = moment()
        await tick(start, 0)
        assert primary.assigned == {"1": "10"} and primary.notices == ["1"]
        await tick(start + timedelta(seconds=1), 1)
        assert primary.assigned == {"1": "10"} and not primary.released
        await tick(start + timedelta(seconds=600), 600)
        assert primary.assigned == {"1": "20"} and primary.released == ["1"]
        primary.occupants["1"] = []
        await tick(start + timedelta(seconds=601), 601)
        assert not primary.assigned

        updated = json.loads(cfg.model_dump_json())
        for bot, original in zip(updated["bots"], data["bots"], strict=True):
            bot["token"] = original["token"]
        updated["servers"][0].update(
            mode="fixed_channels",
            assignments=[{"bot": "primary", "channel_id": "10"}, {"bot": "secondary", "channel_id": "20"}],
        )
        primary.occupants["1"] = [presence("10", "100"), presence("20", "200")]
        cfg = validate_config(json.dumps(updated))
        await coordinator.reload(cfg, start + timedelta(seconds=602))
        secondary.fail = True
        await tick(start + timedelta(seconds=603), 603)
        assert primary.assigned == {"1": "10"} and not secondary.assigned
        secondary.fail = False
        await tick(start + timedelta(seconds=613), 613)
        assert secondary.assigned == {"1": "20"}
        db.set_disabled("1", True)
        await tick(start + timedelta(seconds=614), 614)
        assert not primary.assigned and not secondary.assigned
        await coordinator.close(start + timedelta(seconds=615))
        db.close()

    asyncio.run(run())


def test_primary_command_authorization_privacy_and_secondary_routing(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = config()
        db = Store(tmp_path / "state.sqlite3")
        pipeline = SpeechPipeline(cfg, db, Transcriber())
        listener = DiscordListener(cfg.bots[0], cfg, db, pipeline)
        replies = []

        async def send(text, **kwargs):
            replies.append(text)

        interaction = SimpleNamespace(
            guild_id=1,
            permissions=SimpleNamespace(administrator=False),
            user=SimpleNamespace(id=100),
            response=SimpleNamespace(is_done=lambda: True),
            followup=SimpleNamespace(send=send),
        )
        command = listener.commands.get_command("monitoring")
        await command.callback(interaction, False)
        assert not db.disabled("1") and "administrator" in replies[-1]
        interaction.permissions.administrator = True
        await command.callback(interaction, False)
        assert db.disabled("1")
        await command.callback(interaction, True)
        interaction.permissions.administrator = False
        command = listener.commands.get_command("opt_out")
        await command.callback(interaction)
        assert db.opted_out("1", "100")
        assert not db.opted_out("1", "200") and not db.disabled("1")
        assert not pipeline.allowed("1", "100") and pipeline.allowed("1", "200")
        command = listener.commands.get_command("opt_in")
        await command.callback(interaction)
        assert not db.opted_out("1", "100") and pipeline.allowed("1", "100")
        assert pipeline.allowed("1", "200") and not db.disabled("1")
        assert not listener.client.intents.message_content
        cfg.servers[0].primary_bot = "secondary"
        assert listener._policy(interaction) is None
        await listener.close()
        await pipeline.close()
        db.close()

    asyncio.run(run())


def test_schema_v1_upgrade_preserves_data(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    db = Store(path)
    db.ingest("1", "100", "10", "chunk", moment(), "violet", Lexicon(False, ["violet"]))
    with db.db:
        db.db.execute("DROP TABLE controls")
        db.db.execute("PRAGMA user_version=1")
    db.close()
    db = Store(path)
    assert db.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    db.set_disabled("1", True)
    db.close()
    db = Store(path)
    assert db.disabled("1")
    db.close()


def test_native_cancellation_waits_for_thread_and_discards_result(tmp_path: Path) -> None:
    async def run() -> None:
        db = Store(tmp_path / "state.sqlite3")
        entered, finish = threading.Event(), threading.Event()

        class Blocking:
            def transcribe(self, chunk):
                entered.set()
                assert finish.wait(3)
                return [SpeechWord("violet", 0)]

        pipeline = SpeechPipeline(config(), db, Blocking())
        pipeline.start()
        pipeline.submit(SpeechChunk("1", "10", "100", "chunk", moment(), bytes(38400)))
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        pipeline._task.cancel()
        closing = asyncio.create_task(pipeline.close())
        await asyncio.sleep(0.01)
        assert not closing.done()
        finish.set()
        await closing
        assert db.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        db.close()

    asyncio.run(run())


def test_rtp_gaps_global_buffers_and_unexpected_channels(tmp_path: Path) -> None:
    async def run() -> None:
        cfg = config()
        cfg.transcription.minimum_chunk_seconds = 0.02
        cfg.transcription.max_buffer_bytes = 8000
        db = Store(tmp_path / "state.sqlite3")
        pipeline = SpeechPipeline(cfg, db, Transcriber())
        sink, second = pipeline.new_sink(), pipeline.new_sink()
        client = SimpleNamespace(
            get_guild=lambda s: SimpleNamespace(
                get_member=lambda m: SimpleNamespace(
                    bot=m == 200, voice=SimpleNamespace(channel=SimpleNamespace(id=10))
                )
            )
        )
        guarded = MemberSink(client, sink, "1", "10")
        await guarded.write(frame(100, moment(), channel=20))
        await guarded.write(frame(200, moment()))
        assert pipeline.buffered_bytes == 0
        await guarded.write(frame(100, moment()))
        await sink.write(frame(100, moment() + timedelta(milliseconds=40)))
        assert pipeline.buffered_bytes == 0  # gap included; byte cap discarded the buffer
        await sink.write(frame(100, moment()))
        await second.write(frame(300, moment()))
        await second.write(frame(300, moment() + timedelta(milliseconds=20)))
        assert pipeline.buffered_bytes == 3840 and pipeline.dropped == 1
        await sink.close("test")
        await second.close("test")
        await pipeline.close()
        db.close()

    asyncio.run(run())


def test_independent_servers_and_reports_during_blocked_handshake(tmp_path: Path) -> None:
    async def run() -> None:
        data = config_data()
        second = dict(data["servers"][0], server_id="2")
        data["servers"].append(second)
        cfg = validate_config(json.dumps(data))
        db = Store(tmp_path / "state.sqlite3")
        pipeline = SpeechPipeline(cfg, db, Transcriber())
        pipeline.start()
        blocked = asyncio.Event()
        entered = asyncio.Event()

        class Slow(Worker):
            async def assign(self, server, channel, sink):
                if server == "1":
                    entered.set()
                    await blocked.wait()
                await super().assign(server, channel, sink)

        worker = Slow("primary", {"1": [presence("10", "100")], "2": [presence("20", "200")]})
        coordinator = Coordinator(cfg, db, pipeline, {"primary": worker}, lambda: 0, clock=moment)
        task = asyncio.create_task(coordinator.tick(moment(), 0, include_reports=False))
        await entered.wait()
        await asyncio.sleep(0)
        assert worker.assigned == {"2": "20"}
        await asyncio.wait_for(coordinator.report_tick(moment(), 0), 0.5)
        blocked.set()
        await task
        assert worker.assigned == {"1": "10", "2": "20"}
        await coordinator.close(moment())
        db.close()

    asyncio.run(run())


def test_local_health_without_credentials_and_intentional_setup_exit(tmp_path: Path, capsys) -> None:
    from discuss.cli import main
    from discuss.diagnostics import write_health

    db = Store(tmp_path / "state.sqlite3")
    cfg = config()
    pipeline = SpeechPipeline(cfg, db, Transcriber())
    coordinator = Coordinator(cfg, db, pipeline, {"primary": Worker("primary", {})})
    write_health(tmp_path, coordinator, running=False)
    text = (tmp_path / "health.json").read_text()
    assert cfg.bots[0].token.get_secret_value() not in text and "pcm" not in text
    assert main(["status", "--state-dir", str(tmp_path)]) == 1
    assert main(["--config", str(tmp_path / "missing.json"), "run"]) == 0
    assert "Setup required" in capsys.readouterr().out
    db.close()


def test_runtime_rejects_broad_state_before_model_or_database(tmp_path: Path, monkeypatch) -> None:
    from discuss.application import run_application

    cfg = config()
    cfg.state_dir = str(tmp_path / "broad-state")

    def reject(path):
        raise ConfigError("State permissions must be private")

    monkeypatch.setattr("discuss.application.check_private_file", reject)
    with pytest.raises(ConfigError, match="private"):
        run_application(cfg, tmp_path / "config.json")
    assert not (Path(cfg.state_dir) / "statistics.sqlite3").exists()
