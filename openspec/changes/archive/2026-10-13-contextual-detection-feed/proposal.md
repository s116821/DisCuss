# Proposal

## Why
DEG-42 adds a debug and user-facing feed of recognized curse detections with attributable context. Existing minimal statistics cannot explain recognition mistakes; bounded opt-in excerpts can, without retaining transcripts locally.

## What Changes
- Per-server service-level detection reporting shared by all listener identities; disabled by default. Destination defaults to the leaderboard report channel, with an optional separate text channel.
- Configurable three words before/after by default; overlapping windows for the same member/chunk merge with combined tracked-match counts.
- Immediate dispatch after recognition or a configurable interval digest, paginated at Discord limits.
- Explicit excerpt-publication acknowledgement/visible notice, bounded ephemeral queue/retries/expiry, clearing on privacy/config/lifecycle changes. No SQLite/log/backup excerpt storage.

## Capabilities
### New Capabilities
- `contextual-detection-reporting`: opted-in attributed contextual excerpts, grouping and bounded cadence delivery.
### Modified Capabilities
None: persisted minimal statistics contract remains unchanged; excerpts go to explicitly configured Discord output only.

## Impact
DEG-42, stacked on DisCuss#5. Config/schema/example, speech ingestion integration, shared reporter, primary SDK publisher, diagnostics, privacy/docs and offline tests. No live server access until the user's temporary test setup exists. User clarification: default3 words each side; destination follows existing leaderboard channel unless overridden.
