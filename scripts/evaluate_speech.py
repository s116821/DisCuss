"""Metrics-only synthetic recognition and bounded attributed-load evaluation."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import av
import psutil

from discuss.config import Transcription, validate_config
from discuss.lexicon import Lexicon
from discuss.speech import LocalTranscriber, SpeechChunk, SpeechPipeline
from discuss.storage import Store

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic"


def pcm(path: Path) -> bytes:
    resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
    with av.open(str(path)) as reader:
        frames = [out for frame in reader.decode(audio=0) for out in resampler.resample(frame)]
    frames += list(resampler.resample(None))
    return b"".join(frame.to_ndarray().tobytes() for frame in frames)


async def load_case(root: Path, backend, audio: bytes, count: int) -> dict:
    data = {
        "bots": [{"name": "primary", "token": "offline-fixture-" + "x" * 64}],
        "servers": [
            {
                "server_id": "1",
                "primary_bot": "primary",
                "report_channel_id": "20",
                "voice_channels": ["10"],
                "privacy": {"notice_acknowledged": True},
                "profanity": {"use_builtin_list": False, "custom_words": ["violet moon"]},
            }
        ],
    }
    config = validate_config(json.dumps(data))
    config.transcription.max_queue = 4
    store = Store(root / f"synthetic-{count}.sqlite3")
    pipeline = SpeechPipeline(config, store, backend)
    accepted = 0
    maximum = 0
    pipeline.start()
    started = time.perf_counter()
    try:
        for member in range(count):
            chunk = SpeechChunk("1", "10", str(100 + member), str(member), datetime.now(UTC), audio)
            accepted += pipeline.submit(chunk)
            maximum = max(maximum, len(pipeline.queue))
        while pipeline.processed + pipeline.failures < accepted:
            if pipeline._task is not None and pipeline._task.done():
                raise RuntimeError("Speech evaluation consumer stopped")
            await asyncio.sleep(0.01)
        elapsed = time.perf_counter() - started
        detections = store.db.execute("SELECT member,count(*) FROM events GROUP BY member").fetchall()
        return {
            "offered_streams": count,
            "accepted_streams": accepted,
            "rejected_streams": count - accepted,
            "max_queue_observed": maximum,
            "queue_cap": config.transcription.max_queue,
            "elapsed_seconds": elapsed,
            "processed": pipeline.processed,
            "failures": pipeline.failures,
            "detections_by_synthetic_member": {row[0]: row[1] for row in detections},
            "equivalent_audio_seconds_per_compute_second": accepted * len(audio) / 192000 / elapsed,
        }
    finally:
        await pipeline.close()
        store.close()


def evaluate(root: Path) -> dict:
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stopped = threading.Event()

    def sample() -> None:
        while not stopped.wait(0.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        settings = Transcription()
        started = time.perf_counter()
        backend = LocalTranscriber(root, settings)
        model_load = time.perf_counter() - started
        cases = [
            ("short", pcm(FIXTURES / "short-david.wav"), "violet", 1),
            ("repeated", pcm(FIXTURES / "repeated-zira.wav"), "violet moon", 3),
            ("long", pcm(FIXTURES / "long-david.wav"), "violet moon", 20),
            ("silence", bytes(192000 * 6), "violet", 0),
        ]
        recognition = []
        for name, audio, word, expected in cases:
            chunk = SpeechChunk("1", "10", "100", name, datetime.now(UTC), audio)
            started = time.perf_counter()
            words = backend.transcribe(chunk)
            elapsed = time.perf_counter() - started
            matches = len(Lexicon(False, [word]).matches(" ".join(w.text for w in words)))
            recognition.append(
                {
                    "case": name,
                    "audio_seconds": len(audio) / 192000,
                    "expected_matches": expected,
                    "observed_matches": matches,
                    "inference_seconds": elapsed,
                    "real_time_factor": elapsed / (len(audio) / 192000),
                }
            )
        with tempfile.TemporaryDirectory(prefix="synthetic-evaluation-", dir=root) as temporary:
            load = [asyncio.run(load_case(Path(temporary), backend, cases[1][1], count)) for count in (1, 2, 4, 8)]
        return {
            "platform": platform.platform(),
            "model_id": settings.model_id,
            "revision": settings.revision,
            "device": settings.device,
            "compute_type": settings.compute_type,
            "cpu_threads": settings.cpu_threads,
            "model_load_seconds": model_load,
            "peak_resident_bytes": peak[0],
            "python_process_id": process.pid,
            "inference_subprocesses": len(process.children(recursive=True)),
            "recognition": recognition,
            "attributed_load": load,
            "limitations": "Two artificial US-English voices; short session and burst load only. "
            "No real accents, acoustic mixture, GPU, sustained soak or live Discord qualification.",
        }
    finally:
        stopped.set()
        sampler.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.state_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Synthetic speech metrics saved; no transcripts included.")
