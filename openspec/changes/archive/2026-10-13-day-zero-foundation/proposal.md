# Proposal

## Why

DisCuss currently contains only a README and license. Its first implementation must establish the agreed OnVelvetVelma engineering baseline before feature changes can merge (DEG-1).

## What Changes

- Add uv, Ruff, ty, pytest, dynamic Git-tag packaging and installed metadata version lookup.
- Add scoped semantic PR titles and quality-gated semantic-release with the unchanged upstream analyzer rules.
- Build lean Windows/Linux deployment archives from the release tag, verify metadata, checksums and artifact attestations. Functional release remains disabled until qualification.
- Install independent OpenSpec agent integrations and enforce completed archive/spec consistency in CI.
- Document contributor commands, release setup and safe local testing.

## Capabilities

### New Capabilities

- `release-provenance`: Tag-derived versions, quality gates and verifiable release artifacts.
- `change-lifecycle`: Same-PR proposal, implementation, verification, archive and canonical spec synchronization.

### Modified Capabilities

None; no canonical specs exist yet.

## Impact

Python package scaffold, developer tooling, GitHub Actions and contributor workflow. No Discord connection or application feature behavior is added.
