# Spec Delta

## Purpose

Provide operators a protected, understandable local policy contract and privacy controls without exposing credentials.

## ADDED Requirements

### Requirement: Typed redacted configuration
Configuration MUST bind unique bot credentials to named identities and per-server policies. Unknown versions, disabled/unknown references, conflicting assignments and invalid values MUST fail with errors that omit secret inputs. Missing or placeholder setup SHALL exit intentionally.

#### Scenario: Invalid token configuration
- **WHEN** credentials are missing, placeholders or invalid types
- **THEN** preflight fails with actionable field paths and no token content

### Requirement: Notice and exclusion controls
Monitoring MUST require an acknowledged visible processing notice. Operators SHALL be able to disable monitoring, exclude members, delete local member data and back up state. Excluded members MUST NOT accrue new detections or exposure.

#### Scenario: Opt-out
- **WHEN** a member is excluded before ingestion or a monitoring checkpoint
- **THEN** their new speech detections and monitored exposure are omitted
