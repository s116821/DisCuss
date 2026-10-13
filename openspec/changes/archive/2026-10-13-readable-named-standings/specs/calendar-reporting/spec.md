## ADDED Requirements

### Requirement: Readable named summary reports
Standings and scheduled leaderboards SHALL show separated ranked totals and monitored-hour rates with human-readable local calendar dates. They MUST NOT include per-word breakdowns. Member names SHALL resolve at presentation; unavailable identities SHALL use neutral labels, never numeric IDs. Names MUST be escaped and bounded in UTF16 units; pagination MUST retain section context and deterministic receipts.

#### Scenario: Scheduled delivery after restart
- **WHEN** a queued snapshot is delivered after restart
- **THEN** names resolve within reserved page slots without persisting display names or shifting acknowledged page boundaries

#### Scenario: Earlier queued report
- **WHEN** an earlier ID-based report is pending
- **THEN** publication removes word rows and replaces member IDs with resolved or neutral labels while preserving receipt identity
