# Tasks

## 1. Playback modes

- [x] 1.1 Add first_curse configuration, shared short-interval cadence timing, schema and operator guidance; verify config/default/fallback tests and schema regeneration.
- [x] 1.2 Implement current-speaker eligibility, first-acquired winner and original-listener routing; verify offline timing, bounded clip, candidate changes, opt-out, expiry and multi-listener tests alongside existing modes.

## 2. Integration verification

- [x] 2.1 Verify the full offline suite, Ruff, formatting, ty and strict spec validation; confirm pipeline-to-memory playback coverage and no production test injection.

## Workflow follow-up

- Sync canonical specs and archive this completed change in the implementation PR; verify the archive consistency gate after archival.
- Merge verified checks as s116821 and verify the automatic native release.
- Upgrade the standard local boot service and activate first_curse, preserving its 600-second interval and unrelated protected config; verify fresh speech-ready health and record the outcome in Linear.
