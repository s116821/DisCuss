# Proposal

## Why

Selecting one speaker can leave a replay cycle silent while other monitored people curse. Operators need an optional mode that accepts the first available eligible detection while retaining the familiar randomized listening and replay timing.

## What Changes

- Add `first_curse` alongside the existing `random` and `cadence` playback modes; keep shipped defaults unchanged.
- Accept one qualifying clip from any currently heard eligible human after the randomized listening start. The first detection processed wins, without reordering recognition results by speech timestamp.
- Maintain current eligibility until capture, preserve the winning listener/channel, and retain the existing captured-clip lifecycle and memory bounds.
- Use cadence timing for intervals below 60 seconds while retaining the new mode's all-speaker eligibility.
- Document all three modes and verify routing, timing, eligibility, cancellation and backward compatibility offline.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sampled-voice-playback`: distinguish weighted speaker selection from first-curse eligibility and specify short-interval timing and lifecycle behavior.

## Impact

Playback configuration/schema, controller, tests and operator documentation. No dependency, database or receiver package changes. After release, update the standard local installation to `first_curse`, retaining its 600-second interval, separate text destinations and all unrelated protected settings.
