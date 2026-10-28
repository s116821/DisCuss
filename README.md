# DisCuss

[Service logging](docs/logging.md) provides configurable INFO/WARNING/ERROR events through Linux journald or Windows Event Log, with a protected rotating file fallback.

![DisCuss pirate ship in Discord colors](docs/assets/discuss-banner.svg)

Self-hosted Discord voice profanity competition, with one Python process coordinating one or multiple separately authorized bot identities.

**Current status: working Windows deployment; broader qualification continues.** Protected policy/statistics, one-process coordination, Discord adapters, local speech, privacy controls, reports, diagnostics and native boot installers are implemented. See [runtime setup and limits](docs/runtime.md) and [native install/upgrade guide](scripts/deploy/INSTALL.md). Development releases publish automatically; broader live Discord and actual VM reboot qualification remain documented separately.

Contributor tooling and the purpose of each retained custom script are documented in [scripts/README.md](scripts/README.md).

Start with [Discord application setup and permissions](docs/discord-setup.md), then [configuration](docs/configuration.md), [statistics/operations](docs/statistics.md) and [privacy](docs/privacy.md). Run `discuss --config PATH doctor` for offline setup preflight. The example JSON intentionally contains placeholder setup; never put real credentials in the repository. Canonical tracking is the DisCuss Linear roadmap.

[Broader synthetic measurements](docs/benchmarks/README.md) found missed detections and bounded overload. Recognition accuracy and sustained listener capacity remain unqualified; isolated successful clips cannot establish reliable competition counts.

[Contextual detection reports](docs/detection-reporting.md) can optionally show speaker, recognized excerpt and time. They default to the leaderboard channel, use three words on each side, and support interval digests or a separate channel. Enable only after explicit excerpt-publication acknowledgement; posted Discord text has different retention from local statistics.

[Sampled voice replays](docs/playback.md) optionally replay at most one short in-memory curse clip per cycle, choosing a weighted speaker or accepting the first curse from anyone currently monitored with `first_curse` mode. The default interval is 15 minutes; [configuration](docs/configuration.md#separate-quotes-and-leaderboards) shows a 10-minute override and separate quote/leaderboard channels. Request Speak when installing and verify the bot's effective voice-channel permission before enabling playback. [Quote lookup](docs/quote-history.md) searches the existing Discord report log by person and time without a local quote archive. Scheduled period reports can use `leaderboards.report_channel_id`; it defaults to the existing report channel.

## Development

Install uv and Node.js 24, then run:

```sh
npm ci
uv sync --locked --all-groups --extra runtime
uv run --extra runtime ruff check .
uv run --extra runtime ruff format --check .
uv run --extra runtime ty check
uv run --extra runtime pytest
npm run spec:validate
uv run --extra runtime python scripts/check_openspec.py
uv build
```

Node manifests are required for OpenSpec and the actual semantic-release analyzer; Node is development/release tooling, not a bot runtime requirement. Python 3.12 is selected explicitly in CI and the native installers pin their managed runtime. `npm run test:release` remains an optional release-tool fixture suite rather than a code-check gate.

PowerShell 7 is required for Git fixture operations so workstation identity profiles remain active. Tests use generated local data and do not connect to Discord. Do not use production servers for tests; later live qualification must explicitly opt in to a disposable server and never store third-party audio.

## Contributions

Use scoped Conventional Commit PR titles, e.g. `feat(receiver): add audio sinks` and `docs(setup): clarify installation`. Prefer squash merge. Each substantive change completes proposal, design, delta specs, implementation/tasks, tests and verification, then archive plus canonical spec synchronization **in the same PR**. Root AGENTS.md is the contributor contract. CI rejects active or incomplete changes. Related Linear issues may share one cohesive change.

## Version and releases

Git tags are the sole version source. Hatchling and uv-dynamic-versioning derive PEP 440 metadata; the runtime version helper reads importlib.metadata and falls back to 0.0.0. There is no editable version constant. The configured semantic-release 25 analyzer owns classification: breaking changes major, feats minor, configured maintenance patch, documentation alone no release.

The [three-stage pipeline](docs/releases.md) runs checks once, builds and validates Windows/Linux archives in parallel, then resolves and publishes releases from those saved artifacts. Main resolves the package version before building so the final release can publish those same bytes; final resolution must match the checked source/version before creating a public tag. PRs finish after builds. Release-worthy main merges publish without readiness switches; docs-only changes do not release. SHA-256 checksums and GitHub attestations accompany the exact validated bytes in the same run.

DisCuss GitHub Releases are the canonical application distribution. Lean OS archives contain the wheel, hashed dependencies, native installer/recovery helper, manifest, config example and operator guides. Models stay in external state. The release workflow records the exact receiver dependency, including an immutable development source when configured, and smoke tests the exact extracted assets on both OSes before attesting/uploading them. No managed hosting is planned.

## Provenance and license

GPL-3.0-only; preserve the existing LICENSE. No upstream voice-receiver code is included by this foundation. Any future upstream reuse must retain its original notices and attribution.
