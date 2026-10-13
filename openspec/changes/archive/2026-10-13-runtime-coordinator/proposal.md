# Proposal

## Why

The verified offline policy/statistics core and independent receiver now need a single-process application runtime. Group DEG-13/15–20/32 and remaining adapter work for event/exposure/reporting integration; keep live qualification and final distribution separate.

## What Changes

- Run independent authorized SDK clients, one shared coordinator, speech engine, database and scheduler in one Python process.
- Reconcile Head Hunt/Fixed Channel assignments, mode reloads, idle occupancy, notice delivery and per-identity recovery.
- Segment bounded per-member PCM, run local in-process faster-whisper with a revision-pinned external model cache, and ingest timestamped word matches without retaining transcripts.
- Publish controls/reports only from each server's primary identity; support standings/word stats, privacy opt-out/deletion, admin disable and diagnostics.
- Add model setup and runtime doctor/entrypoint, offline integration fixtures, synthetic benchmark tooling and documentation.
- Use the tested receiver's immutable source archive as a development-only dependency. Final release remains blocked on a qualified independent PyPI version and live acceptance; never call this a release-ready stable dependency.

## Capabilities

### New Capabilities

- `application-runtime`: One-process listener lifecycle, assignment reconciliation and primary-only controls.
- `local-transcription`: Bounded ephemeral per-speaker speech segmentation and local inference/cache lifecycle.

### Modified Capabilities

None; existing policy/statistics contracts are integrated without changing their rules.

## Impact

Optional development runtime dependencies, CLI, coordinator, SDK adapter, SQLite durable admin disable migration and local speech backend. No production Discord server tests, public publishing or service installation in this PR.
