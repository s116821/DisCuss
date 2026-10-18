## MODIFIED Requirements

### Requirement: Stable and conservative report parsing
New report speaker labels SHALL be escaped plain text without mentions, profile links or raw IDs. Lookup MUST match member/time and ignore other authors or malformed lines. Plain-name reports MAY be included only when retained minimal detection metadata confirms attribution unambiguously; otherwise they SHALL be skipped with documented limits. Historical profile-linked reports SHALL remain readable. No unrelated chat or full transcripts SHALL be collected.

#### Scenario: Display name changed
- **WHEN** a member queries a historical linked report after renaming
- **THEN** its stable profile attribution still identifies the member

#### Scenario: Ambiguous legacy report
- **WHEN** a plain-name report cannot be verified against retained minimal detection metadata
- **THEN** it is skipped rather than attributed by guesswork
