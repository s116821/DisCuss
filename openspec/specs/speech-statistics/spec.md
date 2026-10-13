# speech-statistics Specification

## Purpose
Persist only idempotent tracked-word detections and actual monitoring durations needed for period-based entertainment statistics.

## Requirements

### Requirement: Additive normalized encoded lexicon
The built-in dictionary SHALL be packaged in encoded form and enabled by default. Custom words SHALL append regardless of the toggle, with Unicode/case normalization, deduplication and complete word/phrase boundaries. Dictionary changes MUST NOT rewrite historical counts.

#### Scenario: Custom-only matching
- **WHEN** the built-in list is disabled and custom phrases are supplied
- **THEN** only complete normalized custom matches are counted

### Requirement: Minimal idempotent detections
Ingestion SHALL persist server, member, channel, normalized word and UTC detection time exactly once per attributed chunk. Raw audio, full transcripts and credentials MUST NOT be stored. Server statistics MUST remain isolated.

#### Scenario: Retried chunk
- **WHEN** an already committed attributed chunk is replayed
- **THEN** no additional detections are stored even if its active dictionary has changed

### Requirement: Actual monitored duration
Exposure SHALL accrue only for members served by a healthy listener, include silence, exclude unavailable transmitters and union overlapping listener intervals. Queries SHALL clip exposure to the selected window. Restart MUST close leases at their durable checkpoint without accruing downtime.

#### Scenario: Two listeners and restart
- **WHEN** monitoring intervals overlap or an application restarts
- **THEN** overlap counts once and the disconnected interval contributes no exposure
