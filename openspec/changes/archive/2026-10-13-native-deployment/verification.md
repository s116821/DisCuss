# Verification

54 offline tests pass on Windows; dedicated recovery tests verify committed SQLite WAL contents, read-only backup without migrations, page-safe restoration, corruption rejection and stable receiver publication preflight. Ruff/format/ty pass; actual semantic-release analyzer passes13 cases. Tagged v1.2.3 wheel/archive assembly passed, and extracted Windows installer -Plan validated payload hashes and made no install-root changes. PowerShell parser and Bash syntax checks passed. No service/task was registered on this workstation.

CI contains privileged exact-extracted-asset checks on disposable GitHub-hosted Linux/Windows runners: clean install, setup exit, boot definition, rerun, failed candidate recovery, v1.2.4 upgrade, rollback, SQLite/config preservation and uninstall retention. The real release workflow smoke-checks exact tag assets on both OSes before attestation/upload. Remote run38395191340 passed Linux and Windows quality and exact-extracted-asset installation tests, including two sequential version upgrades, failed-candidate recovery, rollback and state-preserving removal. This is startup smoke evidence, not actual reboot or live Discord qualification.

This change implements installer/distribution contracts, not functional v1 qualification. Actual Linux/Windows logged-off reboot tests, live disposable-server DAVE/application acceptance, PyPI trusted-publisher registration and stable receiver pin remain outstanding. Development source bundles are explicitly unqualified and release preflight fails closed. RELEASE_READY is unset.

