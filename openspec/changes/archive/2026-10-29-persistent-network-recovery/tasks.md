# Tasks

## 1. Recovery lifecycle

- [x] 1.1 Implement persistent rate-capped retry and client cleanup/reopen, with offline tests covering outages beyond five attempts, success, independent identities and backoff cancellation.
- [x] 1.2 Classify permanent authorization/setup failures separately and preserve verified TLS and unexpected-error propagation; verify fatal/transport regressions and safe logging.
- [x] 1.3 Document startup recovery and limits; verify documented delays/setup behavior against implementation and tests.

## 2. Validation

- [x] 2.1 Run required lint/format/type/offline/spec checks and record boot evidence plus regression results.

## Workflow follow-up

- Sync/archive the completed specification change in the fix PR and verify archive consistency.
- Publish and merge the verified PR as s116821; wait for official release, verify bundle identity/provenance, then install/restart with protected configuration/state preserved.
- Confirm fresh service health and gateway-ready events under LOCAL SERVICE. Record deployment evidence in DEG-51; do not claim an actual reboot test without performing one.
