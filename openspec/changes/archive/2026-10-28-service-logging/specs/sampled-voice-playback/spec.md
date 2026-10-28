## MODIFIED Requirements

### Requirement: Cadence mode and safe timing fallback
Cadence mode SHALL listen for the selected member from the cycle start and play an acquired clip at its end, with a minimum five-second interval. Random and first_curse modes SHALL require intervals of at least 120 seconds; shorter values MUST fail validation without silently changing timing or eligibility. Configuration MUST bound intervals and clip duration; delayed recognition MUST NOT revive expired cycles.

#### Scenario: Short randomized interval
- **WHEN** random mode is configured with an interval below 120 seconds
- **THEN** configuration validation rejects it with an actionable minimum-interval error

#### Scenario: Short first-curse interval
- **WHEN** first_curse mode is configured with an interval below 120 seconds
- **THEN** configuration validation rejects it without switching to cadence timing or selecting a speaker

#### Scenario: Minimum randomized interval
- **WHEN** random or first_curse is configured with a 120-second interval
- **THEN** validation accepts the configuration and randomized listening/replay timing is retained
