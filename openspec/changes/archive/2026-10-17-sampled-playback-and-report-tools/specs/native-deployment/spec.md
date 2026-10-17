## ADDED Requirements

### Requirement: Identifiable native runtime
The Windows boot installation SHALL expose a recognizable DisCuss executable/process name while retaining one Python application interpreter, protected runtime/state and existing startup/rollback behavior. Naming MUST NOT require user login or affect other Python installations. Platform-controlled process grouping limits SHALL be documented.

#### Scenario: Named Windows startup
- **WHEN** the managed Windows startup task launches the installed application
- **THEN** its application image is identifiable as DisCuss and imports the managed environment's installed dependencies
