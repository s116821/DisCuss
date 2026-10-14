## ADDED Requirements

### Requirement: Automatic Head Hunt channel discovery
Head Hunt SHALL optionally discover all current ordinary voice channels at each evaluation, including additions/removals. Automatic scope MUST use an empty voice_channels list. Optional excluded_channel_ids SHALL subtract candidates while permission, capacity, privacy and affinity filters remain enforced. Explicit channel lists SHALL remain the default; each primary bot listens in one selected channel at a time.

#### Scenario: New channel is populated
- **WHEN** automatic Head Hunt discovers a newly created populated accessible voice channel
- **THEN** that channel participates in the next weighted draw without editing configuration

#### Scenario: Excluded or inaccessible channel
- **WHEN** a discovered voice channel is excluded, forbidden, full or has no eligible members
- **THEN** that channel does not participate in the draw
