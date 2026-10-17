# Verification

## Requirement evidence
- Replay controller tests cover weighted current-person selection, random/cadence scheduling, silent/expired windows, bounded clips and short-interval fallback. Capture-to-memory-source integration verifies retained captured audio after opt-out/departure and cancelled selections before capture. PCM sources emit padded 20 ms frames and release their clip; shutdown/reload clear RAM.
- Quote-history tests cover own-bot filtering, stable renamed-member attribution, conservative unique-event legacy attribution, invalid ranges, DST folds/gaps, read permissions and no quote database. Scans/results/ranges are bounded and private; original report links remain the source.
- Scheduled publication tests verify the independent leaderboard override while existing default/detection routing tests pass. Queue age and inference duration are metadata only; no speculative speech/model changes were made.
- The private Windows interpreter image was executed in an isolated venv with correct prefix and dependency imports. The regression test verifies the actual image path and preserves the CLI executable. Hosted native installer acceptance now checks the saved candidate's named image/imports; execution gates the PR merge.
- Configuration schema and example match the models. Ruff, format, ty and all offline pytest checks passed on Windows/Python 3.12. Canonical specs were semantically synchronized; strict validation and archive consistency are required before publishing this branch.
- Pirate SVG parsed successfully; operator guides describe current defaults, limits, unchanged report destinations and Windows process grouping limitations. Node manifests are required; release fixtures remain optional and Python 3.12 is explicit in CI.

## Operational limits and follow-up
The operator previously confirmed live detection/reporting on Windows; this change was tested offline without production Discord tests. Broader accuracy/load benchmarks and dedicated OS-VM reboot qualification remain pending on their existing Linear issues. Hosted PR/main results, release hashes and the protected local upgrade/restart with default playback enabled are recorded in Linear after execution; this document does not claim them in advance. Captured clips can replay after later member opt-out; the notice and docs say so. RAM clips are lost on restart.
