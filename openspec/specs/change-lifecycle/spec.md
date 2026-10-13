# change-lifecycle Specification

## Purpose
Keep behavioral changes reviewable together with their completed design, verification evidence and canonical specification.

## Requirements

### Requirement: Complete same-PR lifecycle
A substantive behavior change MUST include proposal, design, delta specs, completed tasks, verification and archive in the same PR. Canonical specifications MUST include all new archived requirement changes before merge.

#### Scenario: Active change submitted for merge
- **WHEN** a contributor leaves an active change in the changes directory
- **THEN** the merge-readiness check fails

#### Scenario: Incomplete or unsynchronized archive
- **WHEN** a newly archived change has unfinished tasks or unsynchronized requirements
- **THEN** the merge-readiness check fails
