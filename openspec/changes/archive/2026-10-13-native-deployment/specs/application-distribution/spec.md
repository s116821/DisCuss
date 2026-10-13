## Purpose

Distribute lean native application archives with verifiable tag-derived identity and qualified dependencies rather than development sources.

## ADDED Requirements

### Requirement: Complete verifiable native archives
OS archives SHALL contain the application wheel, hashed runtime requirements, installer/recovery helper, config example, notices, guide and manifest. All version identifiers MUST agree with the release tag. Archive contents MUST exclude model weights and development files. Exact extracted assets SHALL be smoke checked on both supported OSes.

#### Scenario: Corrupt extracted bundle
- **WHEN** an installer sees a file whose SHA-256 disagrees with its manifest
- **THEN** installation fails before changing the existing runtime

### Requirement: Stable receiver release qualification
Application publication MUST reject development receiver sources and require a tested exact stable PyPI receiver pin before release classification. Offline development bundles SHALL be visibly unqualified. Live Discord and actual reboot acceptance MUST be recorded separately from offline or startup smoke evidence.

#### Scenario: Development source dependency
- **WHEN** release preflight inspects an immutable source archive receiver dependency
- **THEN** publication is blocked before a functional tag or release is created
