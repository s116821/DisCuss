# Design

## Context

The canonical Mem design fixes single-process operation, encoded additive lexicon, Head Hunt defaults, calendar-window totals/rates and overlap carryover. This change makes those rules independently testable before live SDK/STT integration.

## Goals / Non-Goals

Goals: deterministic domain logic, durable minimal state, safe configuration and verifiable reports.
Non-goals: Discord connections, speech inference, slash command registration, native startup installation or release qualification.

## Decisions

- Pydantic models forbid unknown fields and expose only server terminology. Token errors omit input values. Bots are named once; all assignments reference enabled identities. Snowflakes are strings to preserve precision. JSON schema_version=1 rejects unknown versions intentionally.
- Defaults: 600-second Head Hunt; weights max=10/min=1/default=1; timezone UTC, ISO Monday weeks; day off/week-month-year on; descending; scaled enabled with 1800 seconds per window. All-disabled cadence retains 30 days by explicit configurable policy. Empty reports are suppressed by default; empty daily reports always suppressed.
- Admin acknowledges a visible listening notice before monitoring starts. Excluded member IDs and runtime opt-out preferences prevent event/exposure processing; server monitoring_enabled allows immediate disable. Silent present humans accrue exposure; server-muted/unavailable transmitters do not. Raw audio/full transcripts are never SQLite columns.
- Head Hunt normalizes eligible channel affinity with finite nonnegative weights, human occupants and permission/capacity exclusions. Inject RNG for deterministic and statistical tests; zero totals idle.
- Store UTC microseconds in SQLite. Ingest a transcript chunk transactionally once per server/member/chunk ID, persisting only normalized detections. Track exposure using idempotent listener/member leases and checkpoints; each query unions overlaps per member. Crash recovery closes open leases at the last durable heartbeat, never extending through downtime.
- Calendar windows are half-open local calendar boundaries converted to UTC. Rates intersect exactly the same reporting window and include qualified zero-count members only on the scaled board.
- Outbox snapshots are unique by server/cadence/window. Cursor advancement and snapshot creation share one transaction. Retry pages with per-page receipts; acknowledge external send ambiguity explicitly. Unacknowledged reports block retirement. Retain only the overlapping tail needed by unfinished shorter windows rather than inventing aggregates.
- Local deletion removes events, exposure, preferences and any queued snapshots containing the member; previously posted Discord messages require operator removal. Backups use SQLite's consistent backup API.

## Risks / Trade-offs

- SQLite protection is OS-local permissions, not encrypted storage → secure external state paths and no token columns.
- Clock changes/DST → aware UTC instants and explicit calendar-boundary fixtures.
- Ambiguous external acknowledgement → at-least-once send ambiguity is documented, receipts prevent normal duplicate retries.
- Live permission validation and delivery are adapter responsibilities → no claim that offline doctor verifies Discord connectivity.
