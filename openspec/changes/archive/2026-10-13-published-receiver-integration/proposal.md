# Integrate the published receiver

## Why
DiscordVoiceReception 1.0.0 is now published on PyPI through trusted OIDC publishing, with wheel/sdist hashes matching its GitHub release. The roadmap's independent-package integration can replace the temporary immutable Git archive.

## What Changes
Pin the runtime receiver to the exact published PyPI version and refresh the locked dependency artifacts. Preserve automatic development releases and immutable-source packaging support. Update integration regression fixtures and runtime/qualification documentation.

## Capabilities
### Modified Capabilities
- `application-distribution`: independently published receiver integration.

## Impact
Runtime dependency declaration/lockfile, release fixtures and operator docs. Receiver runtime source is identical between the old immutable commit and the published tag. No live bot configuration, transcript handling or shared credentials change.
