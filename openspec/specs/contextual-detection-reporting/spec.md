# contextual-detection-reporting Specification

## Purpose
Explain individual recognized curse detections through explicitly opted-in attributable context while keeping local speech ephemeral and reporting bounded.

## Requirements

### Requirement: Explicit contextual publication and destination
Detection reporting SHALL be disabled by default and require excerpt-publication acknowledgement before enablement. The primary publisher SHALL aggregate every listener serving its server. Destination SHALL default to that server's leaderboard channel and permit a separate configured text channel. Visible notice MUST disclose excerpt publication and Discord retention, identifying the destination by its resolved channel name or a generic fallback.

#### Scenario: Use the existing channel
- **WHEN** a server enables detection reporting with acknowledgement and no destination override
- **THEN** its primary bot publishes detection instances to its configured leaderboard channel

#### Scenario: Concise default announcement
- **WHEN** the default processing notice is used with detection reports enabled
- **THEN** one concise sentence names the destination and Discord retention, with personal opt-out/in controls

### Requirement: Attributed grouped context
Instances SHALL display quote first, an em dash, speaker name and earliest detection time in server timezone. Counts and member/server/channel IDs MUST remain internal, omitted from alerts. Context SHALL default to three words per side and preserve case/punctuation. Overlapping windows for one speaker/chunk SHALL merge, counting each match once. Context MUST NOT mix speakers and MAY be clipped or split at chunk/message boundaries.

#### Scenario: Two nearby matches
- **WHEN** two detections from one speaker have overlapping context windows
- **THEN** one grouped instance displays both and internally counts two tracked matches

### Requirement: Immediate or interval digests
Immediate mode SHALL dispatch completed recognition instances without a configured batching delay. A positive interval SHALL combine pending instances in a digest. Messages MUST obey Discord limits, escape untrusted markup and disable mentions/embeds. Delivery tasks MUST NOT block capture/counting/calendar work; normal retry MUST NOT resend acknowledged pages.

#### Scenario: Partial digest delivery
- **WHEN** one page succeeds and a later page fails
- **THEN** only still-pending instances retry, subject to bounded age and privacy checks

### Requirement: Bounded ephemeral excerpts and privacy cleanup
Local snippets MUST remain in bounded memory and never enter SQLite, logs or backups. The feed SHALL discard excerpts on expiry, overload, shutdown/restart, configuration reload or applicable opt-out/deletion/disable/exclusion. Counts MUST remain idempotent regardless of feed delivery. Already posted or externally in-flight content and lost acknowledgements MUST have documented limits.

#### Scenario: Delete before publication
- **WHEN** a member's backing data is deleted while its quote is pending
- **THEN** that quote is removed without altering another member's stored count
