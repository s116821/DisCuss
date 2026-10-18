# Three-stage application pipeline

## Why
The application repeats Python checks across OSes and rebuilds packages after creating a public release. The operator requests one quality gate, parallel platform builds, then final version resolution/publication, with reproducible package metadata and verified publication.

## What Changes
Run code/analyzer/spec/speech checks once on Linux. Preview the candidate with actual semantic-release against a local read-only mirror, build once per platform from a local candidate Git tag (PRs use normal VCS development versions), validate native upgrades using previous published archives and save immutable build artifacts. Finally re-resolve the release, verify source/version/hash receipts, and publish the saved packages with checksums/attestations without rebuilding. PRs omit publication.

## Capabilities
### Modified Capabilities
- `release-provenance`: three ordered stages with reusable build outputs.

## Impact
Application workflows, build/publication helpers, native smoke tag parameters and meaningful pipeline regression tests. Existing semantic-release rules and tag-based version authority remain. Production runtime and local boot task are unaffected.
