## ADDED Requirements

### Requirement: Dedicated period-report destination
Scheduled end-of-period reports SHALL support an optional dedicated text channel. With no override they MUST retain the server's base report destination. The override MUST NOT reroute detection alerts or alter ephemeral standings commands, snapshot identity, retry receipts or calendar boundaries. Destination access failures SHALL retain pending reports for retry.

#### Scenario: Separate scheduled leaderboards
- **WHEN** a dedicated period-report channel is configured
- **THEN** scheduled leaderboards use it while detection alerts keep their independently configured/default destination
