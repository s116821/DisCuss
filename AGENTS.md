# DisCuss contributor instructions

Use GitHub CLI for GitHub operations. On this workstation use git through PowerShell with profiles loaded; preserve the identity hook. Verify authenticated identity and repository permissions before writes. Use process-local credentials when another worker may use a different account. Never change global authentication or Git configuration.

## OpenSpec lifecycle

Almost all substantive behavior changes require a repo-local OpenSpec change. Complete proposal, design, delta specs and tasks before implementation. Implement and test, verify against every requirement, archive the completed change and sync canonical openspec/specs in the SAME PR. One cohesive change may cover related Linear issues. Do not merge active changes or incomplete archived tasks. Trivial docs/format maintenance that changes no behavior may omit a change; state the exemption in the PR. CI enforces canonical validation and archive consistency. User authorization to implement a roadmap covers the full lifecycle without a separate planning approval.

## Quality and release

Run npm ci, uv sync --locked --all-groups, uv run ruff check ., uv run ruff format --check ., uv run ty check, uv run pytest, npm run spec:validate and uv run python scripts/check_openspec.py. Git tags are the sole version source; no static version field or duplicate commit classifier. Preserve the actual semantic-release analyzer. Evaluate and publish releases automatically after successful main quality gates; document live/reboot qualification separately without readiness switches.

## Safety and terminology

Tests are offline by default. No production Discord server testing. Live acceptance requires explicit opt-in and a disposable test server. Never commit or print tokens, keys, raw audio or unrelated transcripts. Use server terminology in external interfaces; SDK names remain at the adapter boundary.

Release analyzer fixture tests (`npm run test:release`) remain available for deliberate release-tool changes; they are not an ordinary quality gate. CI selects Python 3.12 explicitly. Node manifests pin OpenSpec and the actual semantic-release toolchain.
