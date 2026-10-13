## MODIFIED Requirements

### Requirement: Qualified publication with integrity evidence
Every successful main-branch quality run SHALL evaluate releases with the configured semantic-release analyzer, without a readiness variable or manual qualification gate. Published artifacts SHALL have SHA-256 checksums and attestations. Library PyPI publication SHALL automatically consume artifacts from a successful main push using a standalone trusted OIDC workflow, with retry support. Live and reboot qualification evidence SHALL remain documented separately from release automation.

#### Scenario: Development merge
- **WHEN** a release-worthy development change merges to main and quality succeeds
- **THEN** its tag-derived GitHub release and verified assets are published without readiness configuration

#### Scenario: Trusted publisher retry
- **WHEN** the owner registers the PyPI trusted publisher after an upload failed
- **THEN** the original successful CI run's verified distributions can be retried without rebuilding or changing their version
