# local-transcription Specification

## Purpose
Recognize ephemeral member-attributed speech locally with bounded resource use, reproducible cached models and correct event timing.

## Requirements

### Requirement: Bounded attributed speech chunks
PCM buffers SHALL remain separated by server/channel/member and bounded by bytes, duration and stream count. Silence SHALL segment speech without defining monitoring exposure. Handoff/opt-out/shutdown MUST terminate or discard stale buffers while preserving attribution.

#### Scenario: Overlapping speakers
- **WHEN** two members speak at once
- **THEN** their audio is segmented into independent attributed chunks without speaker mixing

### Requirement: In-process local inference and model lifecycle
Speech inference SHALL run locally within the application process without blocking its asyncio loop. Model setup MUST fetch a pinned revision into an external cache; normal startup MUST load local files only. Missing models, queue overload and cancellation SHALL have bounded predictable behavior.

#### Scenario: Model not prepared
- **WHEN** normal startup cannot find the configured local model
- **THEN** it exits intentionally with setup guidance and makes no implicit model download

### Requirement: Timestamped minimal detection and report fencing
Recognition SHALL preserve per-word timing for minimal tracked detections, discard unrelated speech text/audio and respect current exclusions. Reports MUST wait until captured speech preceding a boundary has been processed or discarded, while idle scheduling remains independent of listener occupancy.

#### Scenario: Inference crosses midnight
- **WHEN** a captured utterance from before midnight finishes inference after the boundary
- **THEN** its detections remain in the correct earlier window before that report snapshot is queued
