# native-deployment Specification

## Purpose
Provide native self-hosted boot startup and recoverable updates while preserving protected operator configuration, statistics and model caches.

## Requirements

### Requirement: Protected independent boot runtime
Installation SHALL create an isolated pinned managed Python environment and one least-privileged OS startup registration that runs while users are logged off. Code and mutable data MUST have separate protected paths. Missing setup SHALL stop intentionally; runtime restarts MUST be bounded.

#### Scenario: Boot with missing credentials
- **WHEN** a newly installed service starts with placeholder configuration
- **THEN** it logs setup guidance and exits without an endless restart loop

### Requirement: Recoverable state-preserving changes
Installation and upgrades MUST inspect existing registrations, reject unrelated collisions and back up configuration, startup definition and SQLite consistently before changing them. Failed candidates SHALL restore the prior registration. Explicit rollback SHALL restore the selected recovery snapshot. Uninstall MUST retain state and caches.

#### Scenario: Candidate installation fails
- **WHEN** dependency or candidate validation fails during upgrade
- **THEN** the existing configuration/state remain preserved and prior startup registration is restored

#### Scenario: Remove startup
- **WHEN** an operator uninstalls the startup registration
- **THEN** credentials, statistics, recovery snapshots and model caches remain available

### Requirement: Identifiable native runtime
The Windows boot installation SHALL expose a recognizable DisCuss executable/process name while retaining one Python application interpreter, protected runtime/state and existing startup/rollback behavior. Naming MUST NOT require user login or affect other Python installations. Platform-controlled process grouping limits SHALL be documented.

#### Scenario: Named Windows startup
- **WHEN** the managed Windows startup task launches the installed application
- **THEN** its application image is identifiable as DisCuss and imports the managed environment's installed dependencies
