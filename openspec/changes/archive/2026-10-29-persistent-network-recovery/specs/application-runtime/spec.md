## ADDED Requirements

### Requirement: Persistent bounded network recovery
Listener identities SHALL retry transient startup or transport failures until connectivity returns or shutdown is requested, without exhausting a lifetime attempt budget. Retry delays MUST be capped at 30 seconds and obsolete client state MUST be released before reopening. TLS verification SHALL remain enabled. Permanent authorization/setup errors MUST stop deliberately. Failures MUST remain isolated and diagnostic logs MUST exclude secrets and speech.

#### Scenario: Boot network unavailable beyond five attempts
- **WHEN** DNS, verified TLS or Discord transport remains unavailable through more than five attempts and later recovers
- **THEN** the same listener task remains alive and reconnects automatically using capped backoff, without requiring a new OS startup trigger

#### Scenario: Permanent setup failure
- **WHEN** credentials or required gateway authorization are invalid
- **THEN** the affected identity stops intentionally with a safe setup diagnostic instead of retrying indefinitely, while healthy identities continue

#### Scenario: Shutdown during backoff
- **WHEN** shutdown is requested while an identity is waiting to retry
- **THEN** pending retry work is cancelled, client resources close and no further connection attempt starts
