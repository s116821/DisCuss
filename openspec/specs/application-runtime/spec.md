# application-runtime Specification

## Purpose
Operate one coordinated Python process across authorized Discord identities with independent server assignments and primary-only controls.

## Requirements

### Requirement: Single-process shared coordinator
All enabled listener clients, speech processing, statistics and reporting SHALL share one Python application process and coordinator. Each identity MUST have at most one voice channel per server. Identity failures and server policies SHALL remain isolated and shutdown MUST release clients, tasks and buffers.

#### Scenario: Secondary identity fails
- **WHEN** one secondary listener loses authorization or connection
- **THEN** its capture/exposure stops while independent healthy assignments continue

### Requirement: Timed policy reconciliation
Head Hunt SHALL evaluate each configured interval, keep a winning current channel, idle with no eligible humans and avoid rerolling on every membership event. Fixed Channels SHALL use the same coordinator for one or multiple identities. Reload MUST disconnect stale assignments before reconciling new ones.

#### Scenario: Mode transition
- **WHEN** a server changes from Head Hunt to Fixed Channels
- **THEN** previous assignments are released and only validated fixed assignments remain

### Requirement: Primary-only notice and controls
Each server's primary identity SHALL publish the visible processing notice before listening and own commands/report posts. Secondary identities MUST NOT duplicate controls or announcements. Monitoring disable/status controls MUST require server administrator authorization. Members SHALL have personal opt-out/in controls but no self-deletion command; opting out MUST preserve collected results and posted reports.

#### Scenario: Unauthorized administrator command
- **WHEN** a non-administrator requests monitoring disable or privileged diagnostics
- **THEN** the command is rejected without modifying server monitoring policy

#### Scenario: Personal participation changes preserve results
- **WHEN** a member opts out and later opts in
- **THEN** only future eligibility changes, collected results and published reports remain, and no delete_self command is available

### Requirement: Capability-based exposure and safe setup
Actual monitoring checkpoints MUST require ready reception and speech admission capability, not recent speaking activity. Missing config/model/native prerequisites SHALL produce actionable secret-safe intentional setup exits. Runtime network faults SHALL use bounded recovery and diagnostics.

#### Scenario: Speech queue saturated
- **WHEN** speech admission becomes unavailable
- **THEN** monitoring exposure pauses until the pipeline can process captured audio again

### Requirement: Explicit member breakdown and named diagnostics
Per-word counts SHALL be available only through the dedicated words command with a required Discord member selection. Public output SHALL use recognizable member, channel, server and bot names rather than numeric identity fields. Unknown or disconnected entities SHALL use neutral labels. Opt-out/in MUST affect only the caller; server-wide monitoring MUST remain administrator-only.

#### Scenario: Member-specific word query
- **WHEN** a user selects a member by name for the words command
- **THEN** only that member's counts in the selected period are shown

#### Scenario: Diagnostics without a channel
- **WHEN** a listener is disconnected or an identity cannot resolve
- **THEN** status uses readable neutral labels without reporting IDs

### Requirement: Persistent bounded network recovery
Listener identities SHALL retry connectivity failures until recovery/shutdown, with delays capped at 30 seconds and closed SDK state reopened. Non-connectivity startup failures MUST exhaust a five-failure budget; connectivity failures SHALL neither consume nor reset it, while gateway readiness MUST reset it. Fatal setup errors SHALL stop immediately and unexpected faults SHALL propagate. TLS verification, identity isolation and content-safe logs MUST be preserved.

#### Scenario: Boot network unavailable beyond five attempts
- **WHEN** DNS, socket reachability, timeouts or ordinary Discord transport disconnections persist through more than five attempts and later recover
- **THEN** the same listener task remains alive and reconnects automatically using capped backoff, without requiring a new OS startup trigger

#### Scenario: Permanent setup failure
- **WHEN** credentials or required gateway authorization are invalid
- **THEN** the affected identity stops intentionally with a safe setup diagnostic instead of retrying indefinitely, while healthy identities continue

#### Scenario: Repeated real startup errors
- **WHEN** five non-connectivity startup failures (such as certificate-verification, HTTP/service/protocol or filesystem errors) occur without gateway readiness, even with intervening connectivity failures
- **THEN** the identity stops with a runtime failure and a safe exhausted-retry diagnostic rather than masking a real error indefinitely

#### Scenario: Recovery resets startup failure budget
- **WHEN** an identity reaches gateway readiness after earlier non-connectivity startup failures
- **THEN** subsequent non-connectivity startup failures receive a fresh five-failure budget

#### Scenario: Shutdown during backoff
- **WHEN** shutdown is requested while an identity is waiting to retry
- **THEN** pending retry work is cancelled, client resources close and no further connection attempt starts
