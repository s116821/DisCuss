# Proposal

## Why
The deployed bot works in the operator's Windows server, and the next iteration adds sampled voice replays and useful access to already-published quotes without turning it into an audio/transcript archive. Reporting destinations, documentation and native process visibility also need the requested polish.

## What Changes
- Add optional, bounded in-memory curse replay: weighted participant selection, default 15-minute randomized timing and a short-interval cadence fallback.
- Query the configured Discord detection-report history by member/time, without persisting quotes locally; retain stable attribution through human-labelled profile links.
- Allow a separate end-of-period report channel with current destination as default.
- Expose transcription lag metadata, investigate obvious delay causes, and give the Windows runtime a recognizable process name without another Python worker.
- Update operator-confirmed deployment docs with pirate/Discord branding; remove .python-version and redundant release self-tests from code-quality jobs in both coordinated repos. Keep Node manifests for actual OpenSpec/semantic-release tooling.

## Capabilities
### New Capabilities
- `sampled-voice-playback`: bounded, privacy-aware sampled replay lifecycle.
- `published-quote-history`: authorized on-demand parsing of published Discord reports.
### Modified Capabilities
- `contextual-detection-reporting`: stable human-labelled attribution and replay-aware notice.
- `calendar-reporting`: configurable dedicated period-report destination.
- `native-deployment`: identifiable single-interpreter Windows runtime.
- `release-provenance`: explicit Python selection and optional release fixture tests.

## Impact
Application configuration/schema, speech/coordinator/Discord adapter, native installer and operator docs; coordinated receiver CI cleanup. No new model, cloud transcription, audio files, quote database, public bot hosting or changes to the local leaderboard channel until separately requested.
