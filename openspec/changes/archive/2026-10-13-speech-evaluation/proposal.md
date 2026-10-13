# Proposal

## Why
One speech clip does not characterize recognition errors or queue pressure. The roadmap needs reproducible synthetic cases and honest resource/throughput evidence on both OSes without collecting member audio.

## What Changes
- Neutral generated short/repeated/long clips, silence, separate attributed simultaneous streams and bounded overload scenarios.
- Metrics-only local model suite with expected counts, elapsed time, RSS, inference subprocess count and queue/drop counters.
- Explicit setup/download in disposable CI, never normal boot. Publish limited artificial-voice results with missing accent/GPU/live coverage clearly stated.

## Capabilities
### New Capabilities
- `speech-evaluation`: reproducible privacy-safe accuracy/resource and bounded-load evaluation.
### Modified Capabilities
None.

## Impact
Partial DEG-26 plus DEG-5 reproducible fixtures. Scripts/tests/metrics docs and both OS CI benchmark stage. Neutral synthetic inputs are not third-party recordings; no real Discord login.
