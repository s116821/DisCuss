# Proposal

## Why

Redirected output currently leaves an empty runtime log during normal operation and silently handled reconnects. Operators need severity-filtered, persistent service diagnostics to distinguish crashes, transport recovery and deliberate assignment changes.

## What Changes

- Configure INFO/WARNING/ERROR thresholds, with INFO including all supported levels and the default remaining INFO.
- Emit timestamped lifecycle, voice/assignment/recovery, playback and processing-failure events with safe metadata.
- Integrate Windows Application Event Log and Linux journald, plus a bounded protected file fallback.
- Apply level changes on policy reload; document native queries, retention and ordinary administrative edits/restarts.
- Release and restart the local service at INFO while preserving its playback interval and unrelated operator settings.
- **BREAKING**: enforce the user-requested 120-second minimum for randomized playback modes; reject shorter values without changing timing mode. Explicit cadence retains its five-second minimum; existing shorter randomized configurations need updating before upgrade.

## Capabilities

### New Capabilities

- `service-logging`: severity thresholds, native background sinks, bounded local diagnostics and content-safe operational events.

### Modified Capabilities

- `sampled-voice-playback`: replace automatic short-interval timing fallback with mode-specific validated minimums.

## Impact

Configuration/schema, logging setup, runtime event instrumentation, both native installers, offline/native verification and operator docs. No new Python dependency, database migration, monitoring mode or Discord permissions. Routine local edits use elevated commands and existing installer controls rather than new one-off scripts.
