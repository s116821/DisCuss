# Spec Delta

## Purpose

Choose eligible voice assignments consistently for one or multiple authorized listener identities inside the bot.

## ADDED Requirements

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
