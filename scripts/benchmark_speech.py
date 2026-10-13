"""Benchmark only synthetic/consented local speech; write metrics, never transcripts."""

from __future__ import annotations

import argparse
import json
import platform
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import av
import psutil

from discuss.config import Transcription
from discuss.lexicon import Lexicon
from discuss.speech import LocalTranscriber, SpeechChunk


def benchmark(state: Path, audio: Path, word: str, repetitions: int) -> dict:
    if not 1 <= repetitions <= 10:
        raise ValueError("Benchmark repetitions must be within 1–10")
    settings = Transcription()
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stopped = threading.Event()

    def sample() -> None:
        while not stopped.wait(0.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        started = time.perf_counter()
        transcriber = LocalTranscriber(state, settings)
        load_seconds = time.perf_counter() - started
        resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
        with av.open(str(audio)) as container:
            frames = [out for frame in container.decode(audio=0) for out in resampler.resample(frame)]
        frames += list(resampler.resample(None))
        pcm = b"".join(frame.to_ndarray().tobytes() for frame in frames)
        lexicon = Lexicon(False, [word])
        runs = []
        for i in range(repetitions):
            chunk = SpeechChunk("1", "10", "100", str(i), datetime.now(UTC), pcm)
            started = time.perf_counter()
            words = transcriber.transcribe(chunk)
            elapsed = time.perf_counter() - started
            runs.append(
                {"inference_seconds": elapsed, "matches": len(lexicon.matches(" ".join(w.text for w in words)))}
            )
        return {
            "fixture": "synthetic-or-consented-local-input",
            "platform": platform.platform(),
            "model_id": settings.model_id,
            "revision": settings.revision,
            "device": settings.device,
            "compute_type": settings.compute_type,
            "cpu_threads": settings.cpu_threads,
            "audio_seconds": len(pcm) / 192000,
            "model_load_seconds": load_seconds,
            "peak_resident_bytes": peak[0],
            "python_process_id": process.pid,
            "inference_subprocesses": 0,
            "runs": runs,
            "limitations": "One controlled fixture; not live Discord, accent coverage or general listener capacity.",
        }
    finally:
        stopped.set()
        sampler.join()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--custom-word", required=True)
    parser.add_argument("--repetitions", default=3, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = benchmark(args.state_dir, args.input, args.custom_word, args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Speech benchmark metrics saved; no audio or transcripts included.")


if __name__ == "__main__":
    main()
