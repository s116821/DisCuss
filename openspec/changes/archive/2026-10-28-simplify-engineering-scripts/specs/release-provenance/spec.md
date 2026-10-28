## MODIFIED Requirements

### Requirement: Three-stage artifact-preserving application publication
Application CI SHALL run code checks once, then parallel OS builds, then main-only publication gated on successful builds. Quality MUST NOT plan versions. Builds SHALL save exact packages and receipts; main builds MAY preview the actual analyzer for a local tag. Standard release integration SHALL verify final source/tag before publishing saved bytes without rebuilding. PRs MUST NOT publish. Git tags remain the version authority.

#### Scenario: Platform build fails
- **WHEN** either platform fails packaging or native installation validation
- **THEN** no public tag or release is created

#### Scenario: Final candidate differs
- **WHEN** final semantic-release resolves a tag or source different from the saved build receipts
- **THEN** publication fails before creating a public tag

#### Scenario: Pull request builds
- **WHEN** a pull request passes code checks
- **THEN** both platform packages and native validation run, with no remote tag or release publication

#### Scenario: Quality has no release orchestration
- **WHEN** the quality job runs on a pull request or main push
- **THEN** it runs checks without release previews, version outputs or publication commands
