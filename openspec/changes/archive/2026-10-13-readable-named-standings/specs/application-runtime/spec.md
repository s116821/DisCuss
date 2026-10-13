## ADDED Requirements

### Requirement: Explicit member breakdown and named diagnostics
Per-word counts SHALL be available only through the dedicated words command with a required Discord member selection. Public output SHALL use recognizable member, channel, server and bot names rather than numeric identity fields. Unknown or disconnected entities SHALL use neutral labels. Opt-out/in MUST affect only the caller; server-wide monitoring MUST remain administrator-only.

#### Scenario: Member-specific word query
- **WHEN** a user selects a member by name for the words command
- **THEN** only that member's counts in the selected period are shown

#### Scenario: Diagnostics without a channel
- **WHEN** a listener is disconnected or an identity cannot resolve
- **THEN** status uses readable neutral labels without reporting IDs
