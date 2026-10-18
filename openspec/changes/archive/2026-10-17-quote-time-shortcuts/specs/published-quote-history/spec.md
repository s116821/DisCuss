## ADDED Requirements

### Requirement: Explicit query time syntax and defaults
Quote queries SHALL accept zero-padded YYYY-MM-DD, dated ISO times and time-only HH:MM with optional UTC offset. Omitted dates SHALL use today's date in the configured server timezone; omitted offsets SHALL use that timezone. Explicit offsets MUST be honored. Hints/errors SHALL explain leading zeros, timezone offsets and defaults. Invalid or ambiguous/nonexistent offset-free local times MUST be rejected; existing range limits SHALL remain enforced.

#### Scenario: Time-only query across UTC midnight
- **WHEN** UTC and the configured timezone have different dates and a member supplies 14:30 or 14:30-05:00
- **THEN** both use the configured timezone's current date; the first uses its timezone and the second uses the supplied offset

#### Scenario: Malformed input or clock change
- **WHEN** a timestamp lacks required leading zeros, has an invalid offset or identifies an ambiguous/nonexistent local time without an offset
- **THEN** the query returns an explanatory error instead of guessing an instant
