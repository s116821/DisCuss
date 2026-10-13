"""Ephemeral per-member segmentation and bounded in-process recognition."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Protocol

import av
import numpy as np

from .config import Config, Transcription
from .lexicon import Lexicon, tokens
from .models import verify_model
from .storage import Store


@dataclass(frozen=True, slots=True)
class SpeechWord:
    text: str = field(repr=False)
    start_seconds: float
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class SpeechChunk:
    server_id: str
    channel_id: str
    member_id: str
    chunk_id: str
    started_at: datetime
    pcm: bytes = field(repr=False)


class Frame(Protocol):
    @property
    def server_id(self) -> int: ...
    @property
    def channel_id(self) -> int: ...
    @property
    def member_id(self) -> int: ...
    @property
    def received_at(self) -> datetime: ...
    @property
    def timestamp(self) -> int: ...
    @property
    def pcm(self) -> bytes | None: ...
    @property
    def concealed(self) -> bool: ...


class Transcriber(Protocol):
    def transcribe(self, chunk: SpeechChunk) -> list[SpeechWord]: ...


class LocalTranscriber:
    def __init__(self, state_dir: Path, settings: Transcription) -> None:
        from faster_whisper import WhisperModel

        path = verify_model(state_dir, settings)
        logging.getLogger("faster_whisper").setLevel(logging.WARNING)
        self.settings = settings
        self.model = WhisperModel(
            str(path),
            device=settings.device,
            compute_type=settings.compute_type,
            cpu_threads=settings.cpu_threads,
            num_workers=1,
            local_files_only=True,
        )

    def transcribe(self, chunk: SpeechChunk) -> list[SpeechWord]:
        samples = np.frombuffer(chunk.pcm, dtype="<i2").reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="stereo")
        frame.sample_rate = 48000
        frame.time_base = Fraction(1, 48000)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
        frames = list(resampler.resample(frame)) + list(resampler.resample(None))
        if not frames:
            return []
        audio = np.concatenate([f.to_ndarray().reshape(-1) for f in frames]).astype(np.float32)
        segments, _ = self.model.transcribe(
            audio,
            language=self.settings.language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt="Transcribe spoken words verbatim, including profanity.",
        )
        return [
            SpeechWord(word.word, float(word.start), float(word.probability))
            for segment in segments
            for word in segment.words or []
        ]


@dataclass(slots=True)
class Buffer:
    started_at: datetime
    last_voice_at: datetime
    pcm: bytearray = field(default_factory=bytearray, repr=False)
    last_timestamp: int | None = None
    last_samples: int = 0


class Segmenter:
    def __init__(
        self, settings: Transcription, emit: Callable[[SpeechChunk], bool], allowed: Callable[[str, str], bool]
    ) -> None:
        self.settings, self.emit, self.allowed = settings, emit, allowed
        self.buffers: dict[tuple[str, str, str], Buffer] = {}
        self.dropped = 0

    @property
    def watermark(self) -> datetime | None:
        return min((b.started_at for b in self.buffers.values()), default=None)

    def discard(self, server: str, member: str | None = None) -> None:
        for key in list(self.buffers):
            if key[0] == server and (member is None or key[2] == member):
                self.buffers.pop(key)

    def feed(self, frame: Frame) -> None:
        if not frame.pcm:
            return
        if len(frame.pcm) > self.settings.max_chunk_seconds * 192000 or len(frame.pcm) % 4:
            self.dropped += 1
            return
        key = (str(frame.server_id), str(frame.channel_id), str(frame.member_id))
        if not self.allowed(key[0], key[2]):
            self.buffers.pop(key, None)
            return
        # Handoffs never mix the same member's old and new channel buffers.
        for old in list(self.buffers):
            if old[0] == key[0] and old[2] == key[2] and old[1] != key[1]:
                self._finish(old)
        samples = np.frombuffer(frame.pcm, dtype="<i2").astype(np.float32) / 32768
        voiced = bool(
            not frame.concealed
            and samples.size
            and float(np.sqrt(np.mean(samples * samples))) >= self.settings.vad_threshold
        )
        buffer = self.buffers.get(key)
        if buffer is not None and buffer.last_timestamp is not None:
            delta = (frame.timestamp - buffer.last_timestamp) % 2**32
            if (
                delta >= 2**31
                or len(buffer.pcm) + max(0, delta - buffer.last_samples) * 4 + len(frame.pcm)
                > self.settings.max_chunk_seconds * 192000
            ):
                self._finish(key)
                buffer = None
            else:
                missing = max(0, delta - buffer.last_samples)
                buffer.pcm.extend(bytes(missing * 4))
        if buffer is None:
            if not voiced:
                return
            if len(self.buffers) >= self.settings.max_speakers:
                self.dropped += 1
                return
            buffer = Buffer(frame.received_at - timedelta(seconds=len(frame.pcm) / 192000), frame.received_at)
            self.buffers[key] = buffer
        if voiced:
            buffer.last_voice_at = frame.received_at
        buffer.pcm.extend(bytes(len(frame.pcm)) if frame.concealed else frame.pcm)
        buffer.last_timestamp, buffer.last_samples = frame.timestamp, len(frame.pcm) // 4
        if sum(len(b.pcm) for b in self.buffers.values()) > self.settings.max_buffer_bytes:
            self.buffers.pop(key, None)
            self.dropped += 1
            return
        elapsed = len(buffer.pcm) / 192000
        silent = (frame.received_at - buffer.last_voice_at).total_seconds()
        if elapsed >= self.settings.max_chunk_seconds or silent >= self.settings.silence_seconds:
            self._finish(key)

    def expire(self, now: datetime) -> None:
        for key, buffer in list(self.buffers.items()):
            if (now - buffer.last_voice_at).total_seconds() >= self.settings.silence_seconds:
                self._finish(key)

    def _finish(self, key: tuple[str, str, str]) -> None:
        buffer = self.buffers.pop(key)
        if len(buffer.pcm) / 192000 < self.settings.minimum_chunk_seconds:
            return
        chunk = SpeechChunk(*key, uuid.uuid4().hex, buffer.started_at, bytes(buffer.pcm))
        if not self.emit(chunk):
            self.dropped += 1


class SpeechPipeline:
    def __init__(self, config: Config, store: Store, transcriber: Transcriber) -> None:
        self.config, self.store, self.transcriber = config, store, transcriber
        self.queue: deque[SpeechChunk] = deque()
        self.segmenters: set[Segmenter] = set()
        self._event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._future: asyncio.Future[list[SpeechWord]] | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-speech")
        self._active: SpeechChunk | None = None
        self._discarded: set[str] = set()
        self._closing = False
        self._failed = False
        self.dropped = self.failures = self.processed = 0

    @property
    def ready(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
            and not self._closing
            and not self._failed
            and len(self.queue) < self.config.transcription.max_queue
        )

    @property
    def buffered_bytes(self) -> int:
        return sum(len(buffer.pcm) for segmenter in self.segmenters for buffer in segmenter.buffers.values())

    def allowed(self, server: str, member: str) -> bool:
        policy = next((s for s in self.config.servers if s.server_id == server), None)
        return (
            policy is not None
            and policy.monitoring_enabled
            and not self.store.disabled(server)
            and member not in policy.privacy.excluded_member_ids
            and not self.store.opted_out(server, member)
        )

    def submit(self, chunk: SpeechChunk) -> bool:
        if self._closing or not self.allowed(chunk.server_id, chunk.member_id):
            return False
        if len(self.queue) >= self.config.transcription.max_queue:
            self.dropped += 1
            return False
        self.queue.append(chunk)
        self._event.set()
        return True

    def watermark(self, now: datetime) -> datetime:
        points = [c.started_at for c in self.queue]
        if self._active is not None:
            points.append(self._active.started_at)
        points.extend(s.watermark for s in self.segmenters if s.watermark is not None)
        return min([now, *points])

    def new_sink(self) -> PipelineSink:
        segmenter = Segmenter(self.config.transcription, self.submit, self.allowed)
        self.segmenters.add(segmenter)
        return PipelineSink(self, segmenter)

    def discard(self, server: str, member: str | None = None) -> None:
        if (
            self._active is not None
            and self._active.server_id == server
            and (member is None or self._active.member_id == member)
        ):
            self._discarded.add(self._active.chunk_id)
        self.queue = deque(
            c for c in self.queue if not (c.server_id == server and (member is None or c.member_id == member))
        )
        for segmenter in self.segmenters:
            segmenter.discard(server, member)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="speech-pipeline")

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while not self._closing or self.queue:
            if not self.queue:
                self._event.clear()
                await self._event.wait()
                continue
            chunk = self.queue.popleft()
            if not self.allowed(chunk.server_id, chunk.member_id):
                continue
            self._active = chunk
            try:
                self._future = loop.run_in_executor(self._executor, self.transcriber.transcribe, chunk)
                words = await asyncio.shield(self._future)
                policy = next(s for s in self.config.servers if s.server_id == chunk.server_id)
                lexicon = Lexicon(policy.profanity.use_builtin_list, policy.profanity.custom_words)
                text = " ".join(w.text for w in words)
                matches = lexicon.matches(text)
                token_times = [
                    chunk.started_at + timedelta(seconds=max(0, w.start_seconds)) for w in words for _ in tokens(w.text)
                ]
                match_times = [token_times[m.token_start] for m in matches]
                if chunk.chunk_id not in self._discarded and self.allowed(chunk.server_id, chunk.member_id):
                    self.store.ingest(
                        chunk.server_id,
                        chunk.member_id,
                        chunk.channel_id,
                        chunk.chunk_id,
                        chunk.started_at,
                        text,
                        lexicon,
                        detection_times=match_times,
                    )
                self.processed += 1
                self._failed = False
            except Exception:
                self.failures += 1
                self._failed = True
            finally:
                self._discarded.discard(chunk.chunk_id)
                self._active = None
                if self._future is not None and self._future.done():
                    self._future = None

    async def close(self) -> None:
        self._closing = True
        self.queue.clear()
        for segmenter in self.segmenters:
            segmenter.buffers.clear()
        self._event.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._future is not None:
            with contextlib.suppress(Exception):
                await asyncio.shield(self._future)
        self._executor.shutdown(wait=True, cancel_futures=True)


class PipelineSink:
    def __init__(self, pipeline: SpeechPipeline, segmenter: Segmenter) -> None:
        self.pipeline, self.segmenter = pipeline, segmenter

    async def write(self, frame: Frame) -> None:
        self.segmenter.feed(frame)
        if self.pipeline.buffered_bytes > self.pipeline.config.transcription.max_buffer_bytes:
            self.segmenter.discard(str(frame.server_id), str(frame.member_id))
            self.pipeline.dropped += 1

    async def close(self, reason: str) -> None:
        for key in list(self.segmenter.buffers):
            self.segmenter._finish(key)
        self.pipeline.segmenters.discard(self.segmenter)
