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
Functional publication MUST remain disabled until explicit qualification readiness is configured. Published artifacts SHALL have SHA-256 checksums and attestations. Library PyPI publication MUST use trusted OIDC credentials.

#### Scenario: Unqualified foundation
- **WHEN** the repository has not passed functional release qualification
- **THEN** quality and packaging checks run but no functional release is published
