## MODIFIED Requirements

### Requirement: Attributed grouped context
Instances SHALL display quote first, an em dash, escaped plain-text speaker name and earliest detection time in server timezone. Mentions, profile links, visible counts and raw IDs MUST be omitted. Context SHALL default to three words per side and preserve case/punctuation. Overlapping windows for one speaker/chunk SHALL merge, counting each match once. Context MUST NOT mix speakers and MAY be clipped or split at chunk/message boundaries.

#### Scenario: Two nearby matches
- **WHEN** two detections from one speaker have overlapping context windows
- **THEN** one grouped instance displays both and internally counts two tracked matches
