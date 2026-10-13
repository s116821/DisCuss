"""Single Python process entrypoint and protected state ownership."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from .config import Config, ConfigError, load_config
from .coordinator import Coordinator
from .diagnostics import write_health
from .discord_adapter import DiscordListener
from .speech import LocalTranscriber, SpeechPipeline
from .storage import Store


def state_path(config: Config, config_path: Path) -> Path:
    path = Path(config.state_dir)
    return path if path.is_absolute() else config_path.resolve().parent / path


def run_application(config: Config, config_path: Path) -> int:
    root = state_path(config, config_path)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
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
    for worker in workers.values():
        worker.coordinator = coordinator
    pipeline.start()
    for worker in workers.values():
        worker.start()
    changed_at = config_path.stat().st_mtime_ns

    async def report_loop() -> None:
        while True:
            write_health(store.path.parent, coordinator)
            await coordinator.report_tick(datetime.now(UTC), time.monotonic())
            await asyncio.sleep(1)

    reports = asyncio.create_task(report_loop(), name="calendar-reports")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGTERM, stopping.set)
    try:
        while not stopping.is_set():
            if all(w._task is not None and w._task.done() for w in workers.values()):
                print("Listener identities stopped; verify bot authorization and network readiness.")
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
                print("Configuration reload rejected; check schema or restart for identity, speech or state changes.")
                return 0
            if reports.done():
                print("Report scheduler stopped; restart after checking local state readiness.")
                return 1
            await coordinator.tick(datetime.now(UTC), time.monotonic(), include_reports=False)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), 1)
        return 0
    finally:
        reports.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reports
        await coordinator.close(datetime.now(UTC))
        write_health(store.path.parent, coordinator, running=False)
