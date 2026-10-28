# Maintenance tooling

Normal orchestration belongs in [.github/workflows/ci.yml](../.github/workflows/ci.yml). Use existing actions/CLIs first; keep custom code only for DisCuss-specific packaging, validation or maintenance. Do not add wrapper files for a few workflow commands.

| Tool | Why it remains |
| --- | --- |
| `package_release.py` | Assemble lean native archives with manifests; reject wrong versions, source commits or changed saved assets before publication. `assemble` and `collect` share one implementation. |
| `deploy/` | Linux/systemd and Windows/Task Scheduler installation, recovery and state preservation; [operator guide](deploy/INSTALL.md). |
| `check_openspec.py` | Validate completed archives against canonical project specs; extends the OpenSpec CLI's schema validation. |
| `evaluate_speech.py` | Reproducible synthetic recognition/load acceptance and metrics, used by quality CI. |
| `benchmark_speech.py` | Optional local speech-performance measurement; no Discord connection. |
| `encode_lexicon.py` | Rebuild the encoded built-in dictionary from a private plaintext input. |
| `git.ps1` | Preserve the workstation's required PowerShell profile/identity hook when Python or Node fixtures invoke Git. |

Privileged native installation acceptance and optional release fixtures live in [tests/tools](../tests/tools). The unused standalone smoke-bundle builder was removed; native CI validates the actual platform build against two previously published releases.

CI runs one quality job, parallel native builds and a final main-only release. Quality does no version planning. Main builds need a candidate tag because the wheel embeds its version; they call the actual configured semantic-release analyzer against their disposable local checkout, without publishing. PRs build the ordinary Git-derived development version. Final publication uses the maintained [semantic-release action](https://github.com/cycjimmy/semantic-release-action) and [exec plugin](https://github.com/semantic-release/exec) to reject a source/tag mismatch before tagging. Artifact transfer and provenance use standard GitHub actions. Publication reuses the exact tested files.

Deployment sources moved under `scripts/deploy`; downloadable archives retain their flat layout, so installation commands are unchanged. No compatibility shims or duplicate deployment directory are needed.
