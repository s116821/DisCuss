# Design

## Context

The policy PR and receiver PR have passed Windows/Linux CI. Receiver source commit 823f586d0c8504b5b808d60dfc6ef8667b23be18 is public and tested offline but unqualified for PyPI/live release. PyPI name currently returns no published package.

## Goals / Non-Goals

Goals: functional single Python process; health-based exposure; bounded speech work; primary-only commands and restart-safe reports; no secrets/audio/transcripts in logs.
Non-goals: qualified production/live behavior, final PyPI dependency pin, GPU qualification or native startup installer.

## Decisions

- Runtime remains an optional development extra with exact receiver archive content and faster-whisper 1.2.1. Final distribution gate requires replacing source reference with a stable qualified PyPI pin. No duplicate software version logic.
- Coordinator uses listener protocols and deterministic clock/RNG seams. Head Hunt draws only each configured interval, keeps a winning current channel, idles with nobody eligible; fixed assignments reconcile through the same path. Reconfiguration disconnects stale assignments and resets speech buffers.
- Each listener name owns one SDK client; client.start tasks share asyncio. Per-server primary handles commands/report delivery. Voice state snapshots enforce permissions/capacity and opt-outs; no privileged message-content intent or text ingestion.
- Post the visible notice to the configured report channel before listening. SDK receive readiness plus speech admission readiness drives monitoring checkpoints. Self-muted silence still counts; server-muted/suppressed users are unavailable. Internal SDK naming stays within the adapter.
- Per-speaker amplitude VAD has bounded PCM bytes, duration and stream count, ends on silence/max length/handoff, and never defines exposure. Native PyAV resamples stereo 48 kHz PCM to mono 16 kHz without a subprocess. Serial in-process inference runs in an executor thread, with a bounded asyncio queue and explicit cancellation/backlog health.
- Pin Systran/faster-whisper-small revision 536b0662742c02347bc0e980a01041f333bce120, CPU int8 default. Explicit model setup downloads a verified-revision snapshot outside releases; startup uses local files only. Word timestamps feed per-token match times at calendar boundaries. No recognition text is logged or persisted beyond minimal matches.
- Add SQLite schema v2 for durable server disable; migrate v1 transactionally preserving counts/exposure/receipts. Privacy preference changes flush pending speaker buffers and delete local data as requested.
- SDK gateway and faster-whisper debug text are filtered before application logging. No credentials in task/process arguments; application entrypoint takes only protected config path.

## Risks / Trade-offs

- Native inference cannot be forcibly killed inside a thread → bound chunk length, stop admission, await active inference on shutdown and discard cancelled results.
- Amplitude VAD can miss quiet speech → configurable threshold and synthetic tests/benchmarks; no perfect accuracy claim.
- Native CPU/resource benchmarks do not establish live Discord quality → DEG-26/DEG-11/DEG-40 remain evidence gates where not actually exercised.
- Real credentials and disposable server access may be absent → all automated tests offline and no unqualified release.
