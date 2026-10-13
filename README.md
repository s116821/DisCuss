# DisCuss

Self-hosted Discord voice profanity competition, with one Python process coordinating one or multiple separately authorized bot identities.

**Current status: qualification in progress.** Protected policy/statistics, one-process coordination, Discord adapters, local speech, privacy controls, reports, diagnostics and native boot installers are implemented. See [runtime setup and limits](docs/runtime.md) and [native install/upgrade guide](deploy/INSTALL.md). Live Discord, actual VM reboot and stable receiver publication are required before a functional release.

See [configuration](docs/configuration.md), [statistics/operations](docs/statistics.md) and [privacy](docs/privacy.md). Run `discuss --config PATH doctor` for offline setup preflight. The example JSON intentionally contains placeholder setup; never put real credentials in the repository. Canonical tracking is the DisCuss Linear roadmap.

[Broader synthetic measurements](docs/benchmarks/README.md) found missed detections and bounded overload. Recognition accuracy and sustained listener capacity remain unqualified; isolated successful clips cannot establish reliable competition counts.

## Development

Install uv and Node.js 24, then run:

```sh
npm ci
uv sync --locked --all-groups --extra runtime
uv run --extra runtime ruff check .
uv run --extra runtime ruff format --check .
uv run --extra runtime ty check
uv run --extra runtime pytest
npm run test:release
npm run spec:validate
uv run --extra runtime python scripts/check_openspec.py
uv build
```

PowerShell 7 is required for Git fixture operations so workstation identity profiles remain active. Tests use generated local data and do not connect to Discord. Do not use production servers for tests; later live qualification must explicitly opt in to a disposable server and never store third-party audio.

## Contributions

Use scoped Conventional Commit PR titles, e.g. `feat(receiver): add audio sinks` and `docs(setup): clarify installation`. Prefer squash merge. Each substantive change completes proposal, design, delta specs, implementation/tasks, tests and verification, then archive plus canonical spec synchronization **in the same PR**. Root AGENTS.md is the contributor contract. CI rejects active or incomplete changes. Related Linear issues may share one cohesive change.

## Version and releases

Git tags are the sole version source. Hatchling and uv-dynamic-versioning derive PEP 440 metadata; the runtime version helper reads importlib.metadata and falls back to 0.0.0. There is no editable version constant. The configured semantic-release 25 analyzer owns classification: breaking changes major, feats minor, configured maintenance patch, documentation alone no release.

Successful main-branch quality calls the reusable release workflow only when the repository variable `RELEASE_READY=true` has been set **after functional qualification**. Leave it unset for this foundation. The workflow creates the tag, builds from that tag, validates metadata, attaches SHA-256 checksums and GitHub artifact attestations in the same run. It does not depend on GITHUB_TOKEN tag events launching a separate workflow.

DisCuss GitHub Releases are the canonical application distribution. Lean OS archives contain the wheel, hashed dependencies, native installer/recovery helper, manifest, config example and operator guides. Models stay in external state. The release workflow checks the stable PyPI receiver pin before tagging, then smoke tests the exact extracted assets on both OSes before attesting/uploading them. No managed hosting is planned.

## Provenance and license

GPL-3.0-only; preserve the existing LICENSE. Engineering/versioning baseline adapted from s116821/OnVelvetVelma at commit a5964e3fe7d83e7a27d655c324a76eda28cb387c (corrected PR #11). No upstream voice-receiver code is included by this foundation. Any future upstream reuse must retain its original notices and attribution.
