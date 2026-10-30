# Design

## Evidence

Native events show v2.0.1 starting at 17:52:49 CDT after the October 29 reboot. Five login attempts encountered DNS errors, certificate verification errors and a connection error; the final attempt stopped the listener at 17:54:00. Elevated inspection confirmed the task was enabled, used LOCAL SERVICE, had an AtStartup trigger and three one-minute restart attempts configured. It still remained stopped with result 1. No task restart or TLS weakening is a substitute for in-process recovery.

## Decisions

- Keep a cancellable identity loop with exponential delays of 1, 2, 4, 8, 16 and then at most 30 seconds between failures. Only DNS, socket reachability, timeouts and ordinary transport disconnects bypass the five-failure limit. The SDK retains normal gateway reconnection; the outer loop handles failures escaping initial login/start.
- Close and clear SDK state after a retryable failure so a closed HTTP/gateway client can reopen without accumulating sessions or retaining ready/voice caches. Preserve the event handlers/command tree. Check shutdown before another attempt, and propagate cancellation and unexpected programming faults.
- Give each attempt an explicitly owned verified TCP connector and freshly loaded system trust context. A reused import-time aiohttp TLS context could retain a pre-initialization trust snapshot; recreate it without weakening certificate/hostname checks. The pinned SDK's HTTP connector is configured at this adapter boundary, and both context owners close resources on failure/cancellation.
- Preserve a five-failure budget for certificate/TLS errors, payload failures, gateway discovery/protocol errors, HTTP server/rate-limit failures and other non-connectivity OS errors. Connectivity outages neither consume nor reset this budget; gateway readiness resets it. Exhaustion is a runtime failure, preserving bounded OS crash supervision. Invalid credentials, unauthorized/forbidden or invalid HTTP requests, privileged-intent failures and non-recoverable gateway close codes remain immediate intentional setup failures. Certificate errors never bypass the budget and certificate verification is never disabled.
- Keep content-safe event names and numeric attempt/delay/error metadata; no exception bodies, tokens or speech content. Existing OS crash supervision remains bounded and unchanged.

## Validation and Deployment

Use real SDK lifecycle methods with mocked network I/O and virtual sleeps to exceed the old five-attempt boundary, cover different transport errors, recover successfully, preserve peer identity independence and cancel during backoff. Verify non-connectivity errors exhaust exactly five failures, mixed network outages do not mask them, readiness resets the budget, permanent errors stop without retries and unexpected faults propagate. Run existing offline/hosted checks, publish the patch, verify provenance, then use the official elevated installer and inspect real gateway readiness/health logs. Preserve config bytes and startup policy. Do not reboot the workstation or inject production speech/messages for testing.
