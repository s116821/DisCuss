# application-distribution Specification

## Purpose
Distribute lean native application archives with verifiable tag-derived identity and qualified dependencies rather than development sources.

## Requirements

### Requirement: Complete verifiable native archives
OS archives SHALL contain the application wheel, hashed runtime requirements, installer/recovery helper, config example, notices, guide and manifest. All version identifiers MUST agree with the release tag. Archive contents MUST exclude model weights and development files. Exact extracted assets SHALL be smoke checked on both supported OSes.

#### Scenario: Corrupt extracted bundle
- **WHEN** an installer sees a file whose SHA-256 disagrees with its manifest
- **THEN** installation fails before changing the existing runtime

### Requirement: Stable receiver release qualification
Application releases SHALL support exact PyPI receiver pins and immutable HTTPS source archives during development. The archive manifest SHALL record the actual dependency source and whether installation requires a source build. Publication and installation MUST NOT require a qualification flag. Invalid or mutable dependency sources MUST be rejected. Live Discord and actual reboot acceptance MUST be recorded separately from release and startup smoke evidence.

#### Scenario: Development source dependency
- **WHEN** a release uses a receiver archive pinned to a full Git commit
- **THEN** publication and normal installation proceed with hash verification and the exact source recorded in the manifest

#### Scenario: Mutable source dependency
- **WHEN** a receiver dependency refers to a branch or unpinned archive
- **THEN** packaging rejects the non-reproducible dependency
