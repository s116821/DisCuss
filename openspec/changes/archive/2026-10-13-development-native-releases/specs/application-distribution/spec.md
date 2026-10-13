## MODIFIED Requirements

### Requirement: Stable receiver release qualification
Application releases SHALL support exact PyPI receiver pins and immutable HTTPS source archives during development. The archive manifest SHALL record the actual dependency source and whether installation requires a source build. Publication and installation MUST NOT require a qualification flag. Invalid or mutable dependency sources MUST be rejected. Live Discord and actual reboot acceptance MUST be recorded separately from release and startup smoke evidence.

#### Scenario: Development source dependency
- **WHEN** a release uses a receiver archive pinned to a full Git commit
- **THEN** publication and normal installation proceed with hash verification and the exact source recorded in the manifest

#### Scenario: Mutable source dependency
- **WHEN** a receiver dependency refers to a branch or unpinned archive
- **THEN** packaging rejects the non-reproducible dependency
