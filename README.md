# DisCuss

Self-hosted Discord voice profanity competition, with one Python process coordinating one or multiple separately authorized bot identities.

**Current status: engineering foundation.** The coordinator, receiver integration and native installers are not yet implemented. Deployment archives are scaffolds. No functional release is qualified. Follow the DisCuss Linear project (DEG-1 and dependent issues).

## Development

Install uv and Node.js 24, then run:

```sh
npm ci
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
npm run test:release
npm run spec:validate
uv run python scripts/check_openspec.py
uv build
```

PowerShell 7 is required for Git fixture operations so workstation identity profiles remain active. Tests use generated local data and do not connect to Discord. Do not use production servers for tests; later live qualification must explicitly opt in to a disposable server and never store third-party audio.

## Contributions

Use scoped Conventional Commit PR titles, e.g. `feat(receiver): add audio sinks` and `docs(setup): clarify installation`. Prefer squash merge. Each substantive change completes proposal, design, delta specs, implementation/tasks, tests and verification, then archive plus canonical spec synchronization **in the same PR**. Root AGENTS.md is the contributor contract. CI rejects active or incomplete changes. Related Linear issues may share one cohesive change.

## Version and releases

Git tags are the sole version source. Hatchling and uv-dynamic-versioning derive PEP 440 metadata; the runtime version helper reads importlib.metadata and falls back to 0.0.0. There is no editable version constant. The configured semantic-release 25 analyzer owns classification: breaking changes major, feats minor, configured maintenance patch, documentation alone no release.

Successful main-branch quality calls the reusable release workflow only when the repository variable `RELEASE_READY=true` has been set **after functional qualification**. Leave it unset for this foundation. The workflow creates the tag, builds from that tag, validates metadata, attaches SHA-256 checksums and GitHub artifact attestations in the same run. It does not depend on GITHUB_TOKEN tag events launching a separate workflow.

DisCuss GitHub Releases are the canonical application distribution. The foundation bundles contain a wheel and installer scaffolds; native install/upgrade behavior is delivered by later issues. No managed hosting is planned.

## Provenance and license

GPL-3.0-only; preserve the existing LICENSE. Engineering/versioning baseline adapted from s116821/OnVelvetVelma at commit a5964e3fe7d83e7a27d655c324a76eda28cb387c (corrected PR #11). No upstream voice-receiver code is included by this foundation. Any future upstream reuse must retain its original notices and attribution.
