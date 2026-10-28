# Verification

- Offline suite: 155 tests passed, including tagged internal-wheel/flat native archive assembly, Windows PowerShell installer probes, SQLite preservation and source/version/checksum corruption rejection.
- Ruff checks/format and ty pass; all 15 canonical specs and the change validate strictly.
- Optional release fixtures pass: 13 configured analyzer rules plus the exact inline workflow program for docs/fix/feat/breaking history. Local preview leaves tags/source unchanged. The official exec plugin accepts a matching identity and rejects missing/wrong tag/commit.
- Deployment source move preserves the flat downloadable archive and installer invocation contract. Active references/imports use scripts/deploy; historical completed archives remain historical records.
- Routine build/export/download commands are in the workflow. Nine redundant helper files were removed, packaging behavior consolidated, and three acceptance tools moved into tests/tools. Retained custom tools are explained in scripts/README.md.
- No production Discord test, protected configuration edit, local runtime restart or global GitHub authentication change is required for this tooling cleanup.
- Hosted Linux/Windows native results and final publication are tracked in DEG-50 and the implementation PR.

- Asset audit inspected published v2.0.1 archive members and installer consumers: the standalone wheel duplicated both embedded wheels; the source tarball included development tooling. Builds now produce only the internal wheel; publication contains exactly two native bundles and SHA256SUMS. Tests verify target installer selection and embedded wheel byte identity.
