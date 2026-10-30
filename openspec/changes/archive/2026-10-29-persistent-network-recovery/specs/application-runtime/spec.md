## ADDED Requirements

### Requirement: Persistent bounded network recovery
Listener identities SHALL retry connectivity failures until recovery/shutdown, with delays capped at 30 seconds and closed SDK state reopened. Non-connectivity startup failures MUST exhaust a five-failure budget; connectivity failures SHALL neither consume nor reset it, while gateway readiness MUST reset it. Fatal setup errors SHALL stop immediately and unexpected faults SHALL propagate. TLS verification, identity isolation and content-safe logs MUST be preserved.

#### Scenario: Boot network unavailable beyond five attempts
- **WHEN** DNS, socket reachability, timeouts or ordinary Discord transport disconnections persist through more than five attempts and later recover
- **THEN** the same listener task remains alive and reconnects automatically using capped backoff, without requiring a new OS startup trigger

#### Scenario: Permanent setup failure
- **WHEN** credentials or required gateway authorization are invalid
- **THEN** the affected identity stops intentionally with a safe setup diagnostic instead of retrying indefinitely, while healthy identities continue

#### Scenario: Repeated real startup errors
- **WHEN** five non-connectivity startup failures (such as certificate-verification, HTTP/service/protocol or filesystem errors) occur without gateway readiness, even with intervening connectivity failures
- **THEN** the identity stops with a runtime failure and a safe exhausted-retry diagnostic rather than masking a real error indefinitely

#### Scenario: Recovery resets startup failure budget
- **WHEN** an identity reaches gateway readiness after earlier non-connectivity startup failures
- **THEN** subsequent non-connectivity startup failures receive a fresh five-failure budget

#### Scenario: Shutdown during backoff
- **WHEN** shutdown is requested while an identity is waiting to retry
- **THEN** pending retry work is cancelled, client resources close and no further connection attempt starts
