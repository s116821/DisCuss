"""Atomic metadata-only local health snapshots, never credentials or speech."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .coordinator import Coordinator


def write_health(root: Path, coordinator: Coordinator, *, running: bool = True) -> None:
    pipeline = coordinator.pipeline
    snapshot = {
        "updated_at": datetime.now(UTC).isoformat(),
        "running": running,
        "speech_ready": pipeline.ready and running,
        "queue_depth": len(pipeline.queue),
        "buffered_bytes": pipeline.buffered_bytes,
        "processed_chunks": pipeline.processed,
        "dropped_chunks": pipeline.dropped,
        "speech_failures": pipeline.failures,
        "servers": [
            {
                "server_id": server.server_id,
                "mode": server.mode,
                "disabled": coordinator.store.disabled(server.server_id),
                "listeners": [
                    {
                        "identity": name,
                        "channel_id": worker.current_channel(server.server_id),
                        "connected": worker.connected(server.server_id) and running,
                        "capture_ready": worker.capture_ready(server.server_id) and running,
                    }
                    for name, worker in coordinator.listeners.items()
                ],
            }
            for server in coordinator.config.servers
        ],
    }
    descriptor, temporary = tempfile.mkstemp(prefix=".health-", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(snapshot, stream, indent=2)
        os.replace(temporary, root / "health.json")
    finally:
        Path(temporary).unlink(missing_ok=True)
