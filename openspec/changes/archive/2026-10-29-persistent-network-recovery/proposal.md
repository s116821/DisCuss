# Proposal

## Why

The real October 29 reboot launched DisCuss but early DNS/TLS connection failures exhausted five identity attempts and left Task Scheduler at 0x1. Network availability at boot does not establish that Discord can already be reached.

## What Changes

- Keep each listener alive through transient initial-login/transport failures with capped backoff, rather than permanently exhausting a small attempt budget.
- Clean/reopen SDK connection state between attempts and retain immediate shutdown and per-identity isolation.
- Stop deliberately for invalid authorization or permanent gateway setup errors; retain TLS verification and safe operational logs.
- Document boot recovery and add offline outage/recovery/cancellation/fatal-error regressions; publish and install the fix without modifying protected policy/state.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `application-runtime`: persistent rate-bounded transport recovery across boot-time outages with distinct permanent setup failures.

## Impact

Discord adapter retry lifecycle, offline tests and operations guidance. Existing boot registration, least-privileged runtime, token/configuration, recordings policy and data remain unchanged.
