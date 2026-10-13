# Automatic development releases

## Why
The operator explicitly requests end-to-end releases on development merges and removal of readiness gates. Existing manual gates prevent exercising the pipeline.

## What Changes
Remove manual publication/qualification switches, preserve successful CI and artifact integrity, and document observed qualification separately. application-distribution changes are synchronized in this PR.

## Capabilities
### Modified Capabilities
- `application-distribution`: automatic development publication.

## Impact
GitHub Actions, release assembly/installers where relevant, regression tests and operator documentation. No live voice behavior or shared authentication changes.
