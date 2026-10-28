# Tasks

## 1. Logging policy and sinks

- [x] 1.1 Implement INFO/WARNING/ERROR configuration, structured safe formatting, native sinks and bounded protected file fallback; verify threshold, redaction, exception, rotation and sink-failure tests and document config/query behavior.

## 2. Runtime instrumentation and deployment

- [x] 2.1 Instrument lifecycle, reload, aggregate health, voice/assignment/recovery, playback and processing/report failures; verify offline event and reload regressions and document event meanings.
- [x] 2.2 Register the Windows source and explicit journald capture through native installers; verify native smoke queries and document ordinary elevated config edits, restart and log viewing.
- [x] 2.3 Enforce the 120-second randomized-mode minimum without silent fallback; verify both modes' boundary/rejection tests, updated integration timings and conditional schema, and update playback/configuration guidance.

## 3. Integration verification

- [x] 3.1 Run full offline tests, Ruff/format/ty and strict spec validation; verify schema/docs and event content boundaries without production test injection.

## Workflow follow-up

- Sync canonical specs and archive the completed change in the implementation PR; verify archive consistency.
- Push/merge as s116821 after hosted checks, verify release provenance, upgrade/restart the local service at INFO and verify real native/file startup events plus fresh health.
- Preserve playback first_curse/120 seconds, unrelated protected config/state/models and boot startup; use existing installer and ordinary elevated commands without new one-off script files.
