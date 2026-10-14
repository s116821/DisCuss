# monitoring-policy Specification

## Purpose
Choose eligible voice assignments consistently for one or multiple authorized listener identities inside the bot.

## Requirements

### Requirement: Affinity roulette
Head Hunt SHALL sum eligible human weights per channel and draw in proportion to those sums. Ordered priority weights SHALL interpolate max to min; one priority member receives max. Bots, forbidden/full or empty channels and excluded members MUST NOT contribute. Zero total affinity SHALL idle.

#### Scenario: Boundary draw and idle
- **WHEN** a deterministic random draw crosses a channel's cumulative probability boundary
- **THEN** the next weighted channel is selected; zero total produces no selection

### Requirement: Exclusive fixed assignments
Each bot identity MUST have at most one fixed channel per server, with no duplicate channel assignment. One and multiple fixed listeners SHALL use the same policy contract. Head Hunt SHALL use one primary identity.

#### Scenario: Duplicate assignment
- **WHEN** a policy assigns a bot or a channel twice in one server
- **THEN** configuration is rejected before any connection attempt

### Requirement: Automatic Head Hunt channel discovery
Head Hunt SHALL optionally consider every currently discovered ordinary voice channel in its configured server, without a maintained ID allowlist. Newly added or removed channels SHALL take effect at the next evaluation. Automatic scope MUST NOT also specify an explicit voice_channels list. Optional excluded channel IDs SHALL subtract candidates, while permission, capacity, member privacy and affinity filters remain enforced. Explicit channel lists SHALL remain the default; one primary identity listens in one selected channel at a time.

#### Scenario: New channel is populated
- **WHEN** automatic Head Hunt discovers a newly created populated accessible voice channel
- **THEN** that channel participates in the next weighted draw without editing configuration

#### Scenario: Excluded or inaccessible channel
- **WHEN** a discovered voice channel is excluded, forbidden, full or has no eligible members
- **THEN** that channel does not participate in the draw
