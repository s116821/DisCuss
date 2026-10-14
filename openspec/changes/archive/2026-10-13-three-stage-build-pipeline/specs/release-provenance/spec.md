## ADDED Requirements

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
