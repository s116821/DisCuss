# published-quote-history Specification

## Purpose

Retrieve attributable already-published curse quotes from Discord within an authorized member/time query, without maintaining another content archive.

## Requirements

### Requirement: Authorized bounded Discord quote lookup
A member/time-range command SHALL scan only the primary bot's messages in the configured detection-report channel, with bounded history/results and no local quote persistence. Both requester and bot MUST have channel/history access. Replies SHALL use human labels and original-message links, escape mentions and remain ephemeral. Invalid ranges and unavailable permissions MUST return clear errors.

#### Scenario: Requester cannot view report channel
- **WHEN** a requester lacks access to the configured detection-report history
- **THEN** the command returns no quotes and explains the required channel access

### Requirement: Stable and conservative report parsing
New report speaker labels SHALL be escaped plain text without mentions, profile links or raw IDs. Lookup MUST match member/time and ignore other authors or malformed lines. Plain-name reports MAY be included only when retained minimal detection metadata confirms attribution unambiguously; otherwise they SHALL be skipped with documented limits. Historical profile-linked reports SHALL remain readable. No unrelated chat or full transcripts SHALL be collected.

#### Scenario: Display name changed
- **WHEN** a member queries a historical linked report after renaming
- **THEN** its stable profile attribution still identifies the member

#### Scenario: Ambiguous legacy report
- **WHEN** a plain-name report cannot be verified against retained minimal detection metadata
- **THEN** it is skipped rather than attributed by guesswork
