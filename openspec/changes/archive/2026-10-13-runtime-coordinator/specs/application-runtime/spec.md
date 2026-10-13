# Spec Delta

## Purpose

Operate one coordinated Python process across authorized Discord identities with independent server assignments and primary-only controls.

## ADDED Requirements

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
Each server's primary identity SHALL publish the visible processing notice before listening and own commands/report posts. Secondary identities MUST NOT duplicate controls or announcements. Monitoring disable/status controls MUST require server administrator authorization; members SHALL have opt-out and local deletion controls.

#### Scenario: Unauthorized administrator command
- **WHEN** a non-administrator requests monitoring disable or privileged diagnostics
- **THEN** the command is rejected without modifying server monitoring policy

### Requirement: Capability-based exposure and safe setup
Actual monitoring checkpoints MUST require ready reception and speech admission capability, not recent speaking activity. Missing config/model/native prerequisites SHALL produce actionable secret-safe intentional setup exits. Runtime network faults SHALL use bounded recovery and diagnostics.

#### Scenario: Speech queue saturated
- **WHEN** speech admission becomes unavailable
- **THEN** monitoring exposure pauses until the pipeline can process captured audio again
