# Design

## Context

See proposal.md. The wheel embeds its version, so a candidate is needed before the native installers can validate the final bytes. Final semantic-release remains authoritative.

## Decisions

- Retain quality -> parallel build -> release. Quality has no release outputs or analyzer execution. Main build jobs call the pinned semantic-release API inline, against their disposable checkout's local Git repository, using the existing analyzer configuration. No mirror, remote push, token with write privileges, or extra planner script is required. PR builds use their ordinary tag-derived development version.
- Use cycjimmy/semantic-release-action for publication and @semantic-release/exec for the pre-tag identity check. Preserve configured analyzer rules and the tag-only version source.
- Put uv build/export and previous-release download commands directly in the workflow. Retain one Python package_release helper for bundle manifests, package metadata and saved-byte validation, which have application-specific invariants and meaningful corruption tests.
- Keep deployment in scripts/deploy; preserve the flat archive contract so operators still run install.ps1/install.sh from the extracted archive. Keep native acceptance under tests/tools, since it exercises real OS installers and cannot be replaced by generic artifact actions.
- Remove the obsolete standalone smoke fixture builder and its separate temporary-repository machinery. Keep speech benchmarks, dictionary encoding and OpenSpec validation because they are maintenance/acceptance tools, not publication wrappers.

- Native builds produce a wheel only, embedded in their archive; internal CI receipts still validate that wheel. Final collection publishes only Linux/Windows bundles and SHA256SUMS. DisCuss is a self-hosted application, not a separately published PyPI library. GitHub already provides source links for every release tag. Only the installer for the target OS goes in each bundle. Existing published releases remain intact for upgrade inputs.

## Risks / Trade-offs

- Two platform candidates could disagree: receipt validation rejects mismatched source/tag/platform before publication; the official exec plugin checks final analyzer identity before tagging.
- Workflow commands can grow: inline only simple orchestration, retain native packaging and OS tests as focused modules, document their boundaries.
- Path moves could break installers: update source references and imports while retaining flat packaged contents, then exercise both hosted OS install/upgrade/rollback paths.

## Migration

Merge after offline and hosted validation. No local bot restart or protected configuration edits are necessary. Roll back through a normal revert PR if required.
