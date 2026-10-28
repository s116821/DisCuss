# Tasks

## 1. Native tooling layout

- [x] 1.1 Move deploy into scripts/deploy and native acceptance into tests/tools; update imports, documentation and archive assembly; verify tagged assembly and deployment tests.
- [x] 1.2 Consolidate packaging/collection/dependency metadata, remove unused smoke builder and orchestration wrappers; verify corruption/source/version rejection and document each remaining tool.

## 2. Workflow simplification

- [x] 2.1 Inline build/export/download commands and analyzer preview in builds; replace publication/guard wrappers with standard action/plugin; verify actual-engine docs/fix/feat/breaking and pre-tag guard fixtures.
- [x] 2.2 Update workflow contract tests and contributor guidance; verify quality has no release planning and publication reuses saved artifacts without code-check duplication.

- [x] 2.3 Audit existing published archives and consumers; build only the internal wheel, publish native bundles/checksums only, include the matching installer, and verify artifact contents, corruption rejection and operator guidance.

## 3. Integration

- [x] 3.1 Run required lint, format, types, complete offline tests, release fixtures and strict specification validation; record results and check active references.

## Workflow follow-up

- Sync and archive the specification change in this PR, then verify archive consistency.
- Publish the PR as s116821, verify hosted native builds and update DEG-50 with links and results.
