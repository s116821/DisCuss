## MODIFIED Requirements

### Requirement: Explicit contextual publication and destination
Detection reporting SHALL be disabled by default and require excerpt-publication acknowledgement. The primary publisher SHALL aggregate all server listeners. Destination SHALL default to the server's base report channel, with an optional separate channel. A period-report override MUST NOT reroute detections. The visible notice MUST name the excerpt destination or a generic fallback and disclose enabled ephemeral voice replays.

#### Scenario: Use the existing channel
- **WHEN** a server enables detection reporting with acknowledgement and no destination override
- **THEN** its primary bot publishes detection instances to its configured base report channel

#### Scenario: Concise default announcement
- **WHEN** the default processing notice is used with detection reports enabled
- **THEN** one concise sentence names the destination, replay behavior when enabled, and personal opt-out/in controls

### Requirement: Attributed grouped context
Instances SHALL display quote first, an em dash, human-labelled speaker profile link and earliest detection time in server timezone. Visible counts and raw IDs MUST be omitted. Context SHALL default to three words per side and preserve case/punctuation. Overlapping windows for one speaker/chunk SHALL merge, counting each match once. Context MUST NOT mix speakers and MAY be clipped or split at chunk/message boundaries.

#### Scenario: Two nearby matches
- **WHEN** two detections from one speaker have overlapping context windows
- **THEN** one grouped instance displays both and internally counts two tracked matches
