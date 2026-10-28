from __future__ import annotations

import json
import logging

import pytest

from discuss.config import ConfigError, validate_config
from discuss.service_logging import SafeFormatter, ServiceLogging, WindowsEventHandler, update_logging
from test_config_policy import config_data


@pytest.fixture(autouse=True)
def private_test_paths(monkeypatch):
    monkeypatch.setattr("discuss.service_logging.check_private_file", lambda p: None)


def config(level="INFO"):
    data = config_data()
    data["logging"] = {"level": level}
    return validate_config(json.dumps(data))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("level,expected", [("INFO", 3), ("WARNING", 2), ("ERROR", 1)])
def test_thresholds_and_live_level_changes(tmp_path, level, expected):
    path = tmp_path / "runtime.log"
    with ServiceLogging(path, native=False) as session:
        session.configure(config(level), tmp_path)
        log = logging.getLogger("discuss.test")
        log.info("info_event")
        log.warning("warning_event")
        log.error("error_event")
        assert len(rows(path)) == expected
        update_logging(config("ERROR"))
        log.warning("hidden_after_reload")
        log.error("visible_after_reload")
    assert rows(path)[-1]["event"] == "visible_after_reload"
    assert not any(row["event"] == "hidden_after_reload" for row in rows(path))
    with pytest.raises(ConfigError):
        config("DEBUG")
    assert validate_config(json.dumps(config_data())).logging.level == "INFO"


def test_no_library_bodies_exception_messages_locals_or_tokens(tmp_path):
    path = tmp_path / "runtime.log"
    cfg = config()
    token = cfg.bots[0].token.get_secret_value()
    private_speech = "unrelated conversation fixture"
    with ServiceLogging(path, native=False) as session:
        session.configure(cfg, tmp_path)
        try:
            raise RuntimeError(token + private_speech)
        except RuntimeError:
            logging.getLogger("discuss.test").error("speech_processing_failed", exc_info=True)
            logging.getLogger("external.library").warning("close code 4014: " + token + private_speech, exc_info=True)
        logging.getLogger("discuss.test").info("safe_metadata", extra={"identity": token, "transcript": private_speech})
        logging.getLogger("external.library").info("omitted informational chatter")
    text = path.read_text()
    assert token not in text and private_speech not in text and "transcript" not in text
    events = rows(path)
    assert events[0]["error_type"] == "RuntimeError" and events[0]["stack"]
    assert events[1]["event"] == "library_diagnostic" and events[1]["code"] == 4014
    assert events[2]["identity"] == "[redacted]"
    assert len(events) == 3


def test_file_failure_never_dumps_original_library_record(tmp_path, monkeypatch, capsys):
    with ServiceLogging(tmp_path / "runtime.log", native=False) as session:
        handler = next(h for h in session.handlers if hasattr(h, "maxBytes"))

        def no_space(record):
            raise OSError("private exception fixture")

        monkeypatch.setattr(handler, "shouldRollover", no_space)
        logging.getLogger("external.library").warning("private conversation fixture")
        logging.getLogger("discuss.test").info("continues_without_file")
    output = capsys.readouterr().err
    assert "file_logging_failed" in output and "continues_without_file" in output
    assert "private conversation fixture" not in output and "private exception fixture" not in output


def test_reload_updates_configured_logging_without_replacing_other_settings(tmp_path):
    import asyncio

    from discuss.coordinator import Coordinator
    from discuss.speech import SpeechPipeline
    from discuss.storage import Store
    from test_runtime import Transcriber, Worker, moment

    async def run():
        cfg = config()
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Transcriber())
        worker = Worker("primary", {"1": []})
        coordinator = Coordinator(cfg, store, pipeline, {"primary": worker})
        path = tmp_path / "runtime.log"
        with ServiceLogging(path, native=False) as session:
            session.configure(cfg, tmp_path)
            updated = cfg.model_copy(deep=True)
            updated.logging.level = "ERROR"
            await coordinator.reload(updated, moment())
            logging.getLogger("discuss.test").warning("suppressed_after_reload")
            logging.getLogger("discuss.test").error("retained_after_reload")
        assert rows(path)[-1]["event"] == "retained_after_reload"
        assert not any(r["event"] == "suppressed_after_reload" for r in rows(path))
        assert coordinator.config.servers == cfg.servers
        await coordinator.close(moment())
        store.close()

    asyncio.run(run())


def test_rotation_is_bounded_and_journal_priorities(tmp_path):
    path = tmp_path / "runtime.log"
    with ServiceLogging(path, native=False) as session:
        handler = next(h for h in session.handlers if hasattr(h, "maxBytes"))
        assert handler.maxBytes == 5 * 1024 * 1024 and handler.backupCount == 3
        handler.maxBytes = 1200
        for i in range(100):
            logging.getLogger("discuss.test").info("health_summary", extra={"processed_chunks": i})
    files = list(tmp_path.glob("runtime.log*"))
    assert len(files) == 4 and all(p.stat().st_size <= 1200 for p in files)
    formatter = SafeFormatter(journal=True)
    for level, priority in ((logging.INFO, 6), (logging.WARNING, 4), (logging.ERROR, 3)):
        record = logging.LogRecord("discuss.test", level, __file__, 1, "example_event", (), None)
        assert formatter.format(record).startswith(f"<{priority}>")


def test_unhandled_thread_failure_uses_safe_diagnostics(tmp_path):
    import threading

    path = tmp_path / "runtime.log"
    previous = threading.excepthook

    def fail():
        raise RuntimeError("private speech in thread error")

    with ServiceLogging(path, native=False):
        thread = threading.Thread(target=fail)
        thread.start()
        thread.join()
    assert threading.excepthook is previous
    assert rows(path)[0]["event"] == "thread_failed"
    assert "private speech in thread error" not in path.read_text()


def native_handler(report):
    handler = WindowsEventHandler.__new__(WindowsEventHandler)
    logging.Handler.__init__(handler)
    handler.event_handle = 42
    handler.report = report
    handler.deregister = lambda handle: None
    handler.failed = False
    return handler


def test_windows_event_mapping_and_delivery_failure_fallback(tmp_path, monkeypatch):
    calls = []
    handler = native_handler(lambda *args: calls.append((args[1], json.loads(args[7][0]))) or True)
    path = tmp_path / "runtime.log"
    with ServiceLogging(path, native=False) as session:
        session.add(handler)
        log = logging.getLogger("discuss.test")
        log.info("info_event")
        log.warning("warning_event")
        log.error("error_event")
        assert [kind for kind, data in calls] == [4, 2, 1]
        monkeypatch.setattr("ctypes.WinError", lambda code: OSError("private exception fixture"), raising=False)
        monkeypatch.setattr("ctypes.get_last_error", lambda: 1, raising=False)
        handler.report = lambda *args: False
        log.info("first_failed_delivery")
        log.info("second_after_failure")
    assert handler.failed
    assert sum(row["event"] == "native_logging_unavailable" for row in rows(path)) == 1
    assert rows(path)[-1]["event"] == "second_after_failure"
    assert "private exception fixture" not in path.read_text()


def test_run_cli_persists_startup_and_safe_fatal_failure(tmp_path, monkeypatch):
    from discuss.cli import main

    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data()))
    monkeypatch.setattr("discuss.config.check_private_file", lambda p: None)
    monkeypatch.setattr("discuss.service_logging.WindowsEventHandler", logging.NullHandler)

    def crash(*args):
        raise RuntimeError("unrelated speech fixture")

    monkeypatch.setattr("discuss.application.run_application", crash)
    assert main(["--config", str(path), "run"]) == 1
    events = rows(tmp_path / "state/runtime.log")
    assert [e["event"] for e in events] == ["service_starting", "service_failed"]
    assert events[-1]["error_type"] == "RuntimeError"
    assert "unrelated speech fixture" not in (tmp_path / "state/runtime.log").read_text()


def test_assignment_events_distinguish_recovery_from_policy_move(tmp_path, caplog):
    import asyncio
    from datetime import timedelta

    from discuss.coordinator import Coordinator
    from discuss.speech import SpeechPipeline
    from discuss.storage import Store
    from test_runtime import Transcriber, Worker, moment, presence

    async def run():
        cfg = config()
        store = Store(tmp_path / "stats.sqlite3")
        pipeline = SpeechPipeline(cfg, store, Transcriber())
        worker = Worker("primary", {"1": [presence("10", "100")]})
        coordinator = Coordinator(cfg, store, pipeline, {"primary": worker}, draw=lambda: 0, clock=moment)
        await coordinator.tick(moment(), 0)
        worker.connected_flag, worker.fail = False, True
        await coordinator.tick(moment() + timedelta(seconds=1), 1)
        await coordinator.tick(moment() + timedelta(seconds=2), 2)
        assert sum(r.msg == "assignment_retry_scheduled" for r in caplog.records) == 1
        assert any(r.msg == "assignment_requested" and r.reason == "connection_recovery" for r in caplog.records)
        await coordinator.close(moment() + timedelta(seconds=3))
        store.close()

    caplog.set_level(logging.INFO)
    asyncio.run(run())


def test_module_entrypoint_retains_application_startup_and_error_events(tmp_path, monkeypatch):
    import runpy
    import warnings

    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data()))
    monkeypatch.setattr("discuss.config.check_private_file", lambda p: None)
    monkeypatch.setattr("discuss.service_logging.WindowsEventHandler", logging.NullHandler)

    def crash(*args):
        raise RuntimeError("private failure fixture")

    monkeypatch.setattr("discuss.application.run_application", crash)
    monkeypatch.setattr("sys.argv", ["discuss", "--config", str(path), "run"])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="'discuss.cli' found in sys.modules", category=RuntimeWarning)
        with pytest.raises(SystemExit) as stopped:
            runpy.run_module("discuss.cli", run_name="__main__")
    assert stopped.value.code == 1
    events = rows(tmp_path / "state/runtime.log")
    assert [e["event"] for e in events] == ["service_starting", "service_failed"]
    assert all(e["logger"] == "discuss.cli" for e in events)
    assert "private failure fixture" not in (tmp_path / "state/runtime.log").read_text()
