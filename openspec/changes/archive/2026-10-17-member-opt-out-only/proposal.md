# Proposal

## Why
Members should be able to stop and resume future participation without erasing results already collected or reported. The operator requested removal of the self-service deletion command.

## What Changes
- **BREAKING**: remove `/discuss delete_self` from registered commands.
- Preserve personal opt-out/in, collected statistics, posted reports, and operator-only local maintenance.
- Update help and cover command availability and opt-out/in data preservation offline.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `application-runtime`: primary controls provide personal opt-out/in without member self-deletion.

## Impact
Discord command registration, runtime documentation, existing command tests and one canonical requirement. No storage migration or changes to operator CLI maintenance.
