# Proposal

## Why

The previous CI cleanup reduced jobs but retained a chain of active custom orchestration scripts. Normal release plumbing should be visible in the workflow, with custom code reserved for application-specific packaging and validation.

## What Changes

- Replace release wrappers with the maintained semantic-release action/plugin and short workflow commands.
- Keep version planning out of quality; main platform builds use the actual analyzer to determine their local build tag.
- Consolidate native archive assembly and saved-artifact verification in one packaging helper; remove the unused fixture builder.
- Move deployment tooling and its guide to scripts/deploy; group standalone acceptance helpers under tests/tools.
- Update active references and document why each remaining custom tool exists.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-provenance`: quality performs no release planning; standard publication integration preserves the tested artifact identity and three gates.

## Impact

CI, release plugin configuration, scripts, installer source paths, contributor guidance and tests. Native release archive layout and the installed service/configuration remain compatible.
