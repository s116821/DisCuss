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

### Requirement: Independent published receiver integration
The application SHALL support consuming the independently published receiver through an exact PyPI version pin and hashed runtime artifacts. Native release manifests SHALL identify that package version and installers SHALL use the corresponding locked distributions. Immutable development sources remain supported without readiness gates.

#### Scenario: Published receiver consumed by the application
- **WHEN** the runtime dependency is pinned to a published receiver version
- **THEN** the lockfile and exported runtime requirements reference its verified PyPI distributions, and native release manifests identify that version rather than a development archive

### Requirement: Native application download surface
DisCuss releases SHALL upload only the Windows installer ZIP, Linux installer tarball and their SHA-256 checksum file, with provenance. The application wheel SHALL be embedded in each native bundle rather than published separately; application builds MUST NOT produce a redundant Python source distribution. Each bundle SHALL include its target OS installer. GitHub-generated source links remain available separately.

#### Scenario: Application release downloads
- **WHEN** a DisCuss release publishes after both native builds pass
- **THEN** its uploaded download assets are the two tested native bundles and their checksums, with no standalone wheel or Python source tarball

#### Scenario: Native installer consumes internal wheel
- **WHEN** an operator extracts the bundle for their operating system
- **THEN** its matching installer installs the embedded version-matching wheel and does not require a separate Python package download from the release
