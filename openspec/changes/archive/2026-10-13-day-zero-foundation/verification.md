# Verification — day-zero foundation

Verified locally on Windows x64, CPython 3.12.15, uv 0.13.0 and Node 24.19.0.

- Ruff lint, format and ty pass.
- 12 pytest checks pass, including a real isolated Git v1.2.3 build through PowerShell, wheel/sdist metadata verification, release asset/checksum assembly and mismatch rejection.
- 13 behavioral fixture commits pass against the actual configured semantic-release commit analyzer (including docs no-release and both breaking syntax forms).
- OpenSpec strict change validation passes; completed tasks are archived and canonical sync is checked before committing.
- Tests demonstrate rejection of active changes, unfinished tasks and unsynchronized archived requirements.
- PR/title checks and quality dependency are covered. GitHub Actions Windows/Linux matrix is required after push; local success is not claimed as Linux qualification.
- No Discord access, production server tests, tokens, raw voice samples or application service installations.
- RELEASE_READY and PyPI publisher readiness remain disabled by default; functional qualification is outside this foundation.
