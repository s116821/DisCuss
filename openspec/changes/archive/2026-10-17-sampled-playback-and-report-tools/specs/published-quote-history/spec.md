## Purpose
Retrieve attributable already-published curse quotes from Discord within an authorized member/time query, without maintaining another content archive.

## ADDED Requirements

### Requirement: Authorized bounded Discord quote lookup
A member/time-range command SHALL scan only the primary bot's messages in the configured detection-report channel, with bounded history/results and no local quote persistence. Both requester and bot MUST have channel/history access. Replies SHALL use human labels and original-message links, escape mentions and remain ephemeral. Invalid ranges and unavailable permissions MUST return clear errors.

#### Scenario: Requester cannot view report channel
- **WHEN** a requester lacks access to the configured detection-report history
- **THEN** the command returns no quotes and explains the required channel access

### Requirement: Stable and conservative report parsing
New report speaker labels SHALL link to stable Discord profiles without displaying raw IDs. Lookup MUST match member/time and ignore other authors or malformed lines. Legacy plain-name reports MAY be included only when existing minimal detection metadata confirms attribution unambiguously; otherwise they SHALL be skipped with documented limits. No unrelated chat or full transcripts SHALL be collected.

#### Scenario: Display name changed
- **WHEN** a member queries a new linked report after renaming
- **THEN** its stable profile attribution still identifies the member

#### Scenario: Ambiguous legacy report
- **WHEN** an old plain-name report cannot be verified against retained minimal detection metadata
- **THEN** it is skipped rather than attributed by guesswork
