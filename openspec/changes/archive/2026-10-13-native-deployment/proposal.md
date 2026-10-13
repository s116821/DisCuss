# Proposal

## Why
The offline runtime needs repeatable native boot deployment without overwriting credentials, state or models. Release archives must be lean, integrity checked and impossible to publish with an unqualified development receiver pin.

## What Changes
- Versioned uv-managed CPython environments, Linux systemd and Windows LocalService startup task installers.
- Pre-mutation backup, candidate verification, rollback and state-preserving removal.
- Tag-derived manifests, hashed runtime requirements, extracted-asset CI smoke checks and public operator guides.
- Enforced stable receiver release pin and explicit release/VM/live qualification gates.

## Capabilities
### New Capabilities
- `native-deployment`: protected boot installation and state-preserving upgrades/rollback.
- `application-distribution`: tag-consistent lean archives and fail-closed publication eligibility.
### Modified Capabilities
None; existing release-provenance gate remains intact.

## Impact
DEG-35–39. Deploy scripts, release assembly/workflow, stdlib backup helper, cross-platform CI and docs. No workstation service registration or real Discord tests; actual reboot and stable PyPI/live qualification remain external evidence requirements.
