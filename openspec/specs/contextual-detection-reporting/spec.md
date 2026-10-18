# contextual-detection-reporting Specification

## Purpose
Explain individual recognized curse detections through explicitly opted-in attributable context while keeping local speech ephemeral and reporting bounded.

## Requirements

### Requirement: Explicit contextual publication and destination
Detection reporting SHALL be disabled by default and require excerpt-publication acknowledgement. The primary publisher SHALL aggregate all server listeners. Destination SHALL default to the server's base report channel, with an optional separate channel. A period-report override MUST NOT reroute detections. The visible notice MUST name the excerpt destination or a generic fallback and disclose enabled ephemeral voice replays.

#### Scenario: Use the existing channel
- **WHEN** a server enables detection reporting with acknowledgement and no destination override
- **THEN** its primary bot publishes detection instances to its configured base report channel

#### Scenario: Concise default announcement
- **WHEN** the default processing notice is used with detection reports enabled
- **THEN** one concise sentence names the destination, replay behavior when enabled, and personal opt-out/in controls

### Requirement: Attributed grouped context
Instances SHALL display quote first, an em dash, escaped plain-text speaker name and earliest detection time in server timezone. Mentions, profile links, visible counts and raw IDs MUST be omitted. Context SHALL default to three words per side and preserve case/punctuation. Overlapping windows for one speaker/chunk SHALL merge, counting each match once. Context MUST NOT mix speakers and MAY be clipped or split at chunk/message boundaries.

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
