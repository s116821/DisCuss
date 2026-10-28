## Purpose

Provide persistent, severity-filtered operational evidence for background service health, voice recovery and policy decisions without retaining conversation content.

## ADDED Requirements

### Requirement: Configurable service severity
The service SHALL accept INFO, WARNING and ERROR logging thresholds in protected configuration, defaulting to INFO. INFO SHALL include all three levels; WARNING SHALL include WARNING and ERROR; ERROR SHALL include ERROR. Invalid levels MUST fail validation. Valid level changes SHALL apply on policy reload without changing monitoring policy.

#### Scenario: Warning threshold
- **WHEN** an operator selects WARNING
- **THEN** routine INFO events are suppressed while WARNING and ERROR remain visible

#### Scenario: Level reload
- **WHEN** a valid logging threshold changes in the running configuration
- **THEN** subsequent events use the new threshold

### Requirement: Persistent native service sinks
Background events SHALL reach Linux journald or Windows Application Event Log with mapped severity and timestamps. Windows installation SHALL register its application source without granting runtime administrator rights. A protected rotating local file SHALL retain at most four five-MiB files. Native sink failure MUST preserve file/console diagnostics and MUST NOT stop monitoring. Existing log-file overrides SHALL remain supported.

#### Scenario: Windows background start
- **WHEN** the installed boot task starts under its runtime account
- **THEN** startup events appear in Application Event Log under DisCuss and in the protected local log

#### Scenario: Journal delivery
- **WHEN** the Linux systemd service emits a warning
- **THEN** journalctl exposes the warning with warning priority

#### Scenario: Native sink unavailable
- **WHEN** native event delivery fails
- **THEN** the service continues with fallback diagnostics and reports the sink failure without recursive logging

### Requirement: Content-safe operational evidence
Logs SHALL identify startup, readiness, shutdown, reload, voice state/assignment/recovery and processing/playback failures, with bounded periodic health summaries. They MUST exclude credentials, raw audio, transcripts and detected-word content. Exception details SHALL retain only safe types, numeric codes and stack locations. External-library messages SHALL be summarized without retaining arbitrary message bodies. Repeated unchanged failures SHALL avoid per-tick flooding.

#### Scenario: Rejoin investigation
- **WHEN** a listener reconnects or changes channel
- **THEN** events distinguish transport/voice state from an application assignment decision, with available routing/reason metadata

#### Scenario: Unsafe exception and library output
- **WHEN** an exception or external log record contains a token or conversation text
- **THEN** retained diagnostics expose safe metadata without that content
