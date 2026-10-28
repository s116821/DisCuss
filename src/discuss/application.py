"""Single Python process entrypoint and protected state ownership."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from .config import Config, ConfigError, check_private_file, load_config
from .coordinator import Coordinator
from .diagnostics import write_health
from .discord_adapter import DiscordListener
from .speech import LocalTranscriber, SpeechPipeline
from .storage import Store

log = logging.getLogger(__name__)


def state_path(config: Config, config_path: Path) -> Path:
    path = Path(config.state_dir)
    return path if path.is_absolute() else config_path.resolve().parent / path


def run_application(config: Config, config_path: Path) -> int:
    root = state_path(config, config_path)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    check_private_file(root)
    lock = FileLock(root / "application.lock")
    try:
        with lock.acquire(timeout=0):
            try:
                transcriber = LocalTranscriber(root, config.transcription)
            except (RuntimeError, OSError):
                raise ConfigError("Speech runtime could not initialize; check model/native prerequisites") from None
            store = Store(root / "statistics.sqlite3")
            store.recover()
            try:
                return asyncio.run(_run(config, store, transcriber, config_path))
            finally:
                store.close()
    except Timeout:
        raise ConfigError("DisCuss is already running for this state directory") from None


async def _run(config: Config, store: Store, transcriber: LocalTranscriber, config_path: Path) -> int:
    pipeline = SpeechPipeline(config, store, transcriber)
    workers = {b.name: DiscordListener(b, config, store, pipeline) for b in config.bots if b.enabled}
    coordinator = Coordinator(config, store, pipeline, workers)

    def loop_error(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        error = context.get("exception")
        log.error("async_task_failed", exc_info=(type(error), error, error.__traceback__) if error else None)

    asyncio.get_running_loop().set_exception_handler(loop_error)
    for worker in workers.values():
        worker.coordinator = coordinator
    pipeline.start()
    for worker in workers.values():
        worker.start()
    changed_at = config_path.stat().st_mtime_ns

    async def report_loop() -> None:
        due = 0.0
        while True:
            write_health(store.path.parent, coordinator)
            if time.monotonic() >= due:
                log.info(
                    "health_summary",
                    extra={
                        "healthy": pipeline.ready,
                        "queue_depth": len(pipeline.queue),
                        "processed_chunks": pipeline.processed,
                        "speech_failures": pipeline.failures,
                        "playback_started": pipeline.playback.played,
                        "playback_failures": pipeline.playback.failures,
                        "playback_skipped": pipeline.playback.skipped,
                        "dropped_chunks": pipeline.dropped,
                        "listeners_ready": sum(
                            w.capture_ready(s.server_id) for w in workers.values() for s in coordinator.config.servers
                        ),
                    },
                )
                due = time.monotonic() + 60
            await coordinator.report_tick(datetime.now(UTC), time.monotonic())
            await asyncio.sleep(1)

    reports = asyncio.create_task(report_loop(), name="calendar-reports")
    log.info("service_ready")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGTERM, stopping.set)
    try:
        while not stopping.is_set():
            if all(w._task is not None and w._task.done() for w in workers.values()):
                log.error("listener_identities_stopped")
                return 0 if any(w.setup_failed for w in workers.values()) else 1
            try:
                modification = config_path.stat().st_mtime_ns
                if modification != changed_at:
                    changed_at = modification
                    updated = load_config(config_path)
                    if state_path(updated, config_path).resolve() != store.path.parent.resolve():
                        raise ConfigError("Restart is required when the state directory changes")
                    await coordinator.reload(updated, datetime.now(UTC))
            except (OSError, ValueError):
                log.error("configuration_reload_rejected", exc_info=True)
                return 0
            if reports.done():
                error = reports.exception()
                log.error(
                    "report_scheduler_stopped", exc_info=(type(error), error, error.__traceback__) if error else None
                )
                return 1
            await coordinator.tick(datetime.now(UTC), time.monotonic(), include_reports=False)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), 1)
        return 0
    finally:
        log.info("service_stopping")
        reports.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reports
        await coordinator.close(datetime.now(UTC))
        write_health(store.path.parent, coordinator, running=False)
        log.info("service_stopped")
