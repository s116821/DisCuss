# Tasks

## 1. Replay policy and lifecycle
- [x] 1.1 Add bounded playback config/controller with weighted selection, randomized/cadence timing, expiry and cancellation; verify deterministic offline timing/weight/privacy tests and document defaults.
- [x] 1.2 Integrate word-timed PCM trimming and in-process Discord playback/cleanup; verify synthetic pipeline, channel-change/opt-out and memory-source tests and replay-aware notice docs.

## 2. Report history and destinations
- [x] 2.1 Add attributable Discord-history member/time lookup without local quote storage; verify parser/DST/access/legacy-attribution tests and document limits.
- [x] 2.2 Add independent scheduled-report destination and queue/recognition lag metadata; verify routing/default/health tests and update configuration/schema docs.

## 3. Native runtime and presentation
- [x] 3.1 Add a recognizable managed Windows runtime image without another Python worker; verify isolated name/import proof and hosted installer contract tests, documenting OS grouping limits.
- [x] 3.2 Refresh README/operator docs and Discord-color pirate artwork to reflect operator-confirmed use and remaining qualification limits; verify links, SVG and generated examples.

## 4. Tooling and integration
- [x] 4.1 Remove .python-version and release self-tests from quality jobs, retain required Node tooling and explicit Python selection; verify coordinated repo workflow/package checks and documentation.
- [x] 4.2 Run required offline quality, schema/spec validation and integration checks; record results and confirm bounded replay/history/personal cleanup without Discord production tests.

## Workflow follow-up
- Sync canonical specs and archive the completed change in this PR; coordinate the receiver cleanup PR as part of DEG-46.
- Merge successful PRs, verify releases, upgrade/restart the protected local bot and enable default replay while preserving token, statistics, model cache and existing report destinations.
