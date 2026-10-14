## ADDED Requirements

### Requirement: Automatic Head Hunt channel discovery
Head Hunt SHALL optionally consider every currently discovered ordinary voice channel in its configured server, without a maintained ID allowlist. Newly added or removed channels SHALL take effect at the next evaluation. Automatic scope MUST NOT also specify an explicit voice_channels list. Optional excluded channel IDs SHALL subtract candidates, while permission, capacity, member privacy and affinity filters remain enforced. Explicit channel lists SHALL remain the default; one primary identity listens in one selected channel at a time.

#### Scenario: New channel is populated
- **WHEN** automatic Head Hunt discovers a newly created populated accessible voice channel
- **THEN** that channel participates in the next weighted draw without editing configuration

#### Scenario: Excluded or inaccessible channel
- **WHEN** a discovered voice channel is excluded, forbidden, full or has no eligible members
- **THEN** that channel does not participate in the draw
