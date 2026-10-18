## MODIFIED Requirements

### Requirement: Primary-only notice and controls
Each server's primary identity SHALL publish the visible processing notice before listening and own commands/report posts. Secondary identities MUST NOT duplicate controls or announcements. Monitoring disable/status controls MUST require server administrator authorization. Members SHALL have personal opt-out/in controls but no self-deletion command; opting out MUST preserve collected results and posted reports.

#### Scenario: Unauthorized administrator command
- **WHEN** a non-administrator requests monitoring disable or privileged diagnostics
- **THEN** the command is rejected without modifying server monitoring policy

#### Scenario: Personal participation changes preserve results
- **WHEN** a member opts out and later opts in
- **THEN** only future eligibility changes, collected results and published reports remain, and no delete_self command is available
