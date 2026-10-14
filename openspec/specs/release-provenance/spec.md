# release-provenance Specification

## Purpose
Give operators and downstream consumers verifiable package versions and release provenance after successful quality checks.

## Requirements

### Requirement: One tag-derived version
The package SHALL derive its version solely from Git tags and expose installed metadata with a 0.0.0 fallback when metadata is absent. A release MUST reject wheel or archive identifiers that disagree with its tag.

#### Scenario: Tagged build
- **WHEN** a package is built at tag v1.2.3
- **THEN** its wheel metadata and release artifact identifiers agree on version 1.2.3

### Requirement: Quality-gated release classification
Main-branch release evaluation SHALL run only after all quality checks succeed. Scoped Conventional Commit titles are required. The configured analyzer SHALL produce no release for docs, minor for feat, patch for configured maintenance types and major for breaking changes.

#### Scenario: Documentation-only merge
- **WHEN** the configured analyzer evaluates a docs-only commit
- **THEN** it produces no release

#### Scenario: Failed quality check
- **WHEN** a main-branch quality check fails
- **THEN** release evaluation does not run

### Requirement: Qualified publication with integrity evidence
Every successful main-branch quality run SHALL evaluate releases with the configured semantic-release analyzer, without a readiness variable or manual qualification gate. Published artifacts SHALL have SHA-256 checksums and attestations. Library PyPI publication SHALL automatically consume artifacts from a successful main push using a standalone trusted OIDC workflow, with retry support. Live and reboot qualification evidence SHALL remain documented separately from release automation.

#### Scenario: Development merge
- **WHEN** a release-worthy development change merges to main and quality succeeds
- **THEN** its tag-derived GitHub release and verified assets are published without readiness configuration

#### Scenario: Trusted publisher retry
- **WHEN** the owner registers the PyPI trusted publisher after an upload failed
- **THEN** the original successful CI run's verified distributions can be retried without rebuilding or changing their version

### Requirement: Three-stage artifact-preserving application publication
Application CI SHALL run code checks once, then parallel OS builds, then main-only publication gated on successful builds. Builds SHALL save exact packages and validation receipts. Final semantic-release MUST match their source/tag before publishing those bytes without rebuilding. PRs MUST NOT publish. A read-only candidate preview MAY precede builds; Git tags remain the version authority.

#### Scenario: Platform build fails
- **WHEN** either platform fails packaging or native installation validation
- **THEN** no public tag or release is created

#### Scenario: Final candidate differs
- **WHEN** final semantic-release resolves a tag or source different from the saved build receipts
- **THEN** publication fails before creating a public tag

#### Scenario: Pull request builds
- **WHEN** a pull request passes code checks
- **THEN** both platform packages and native validation run, with no remote tag or release publication
