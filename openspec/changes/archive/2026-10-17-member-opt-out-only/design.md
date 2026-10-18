# Design

## Decisions
Remove the delete_self registration and callback instead of retaining a command that rejects requests. Primary command synchronization on startup replaces the server command group, removing the old entry. Personal opt-out/in continues to change future eligibility only; existing event/exposure data and posted messages remain intact. Keep operator CLI deletion and retention maintenance unchanged.

## Verification and migration
Extend the existing offline command integration test to check absence of delete_self and preserve recorded counts through opt-out and opt-in. Verify other members and administrator controls remain independent. Document the command removal and retention boundary, synchronize the full requirement including its existing authorization scenario, and archive before merge. A restart synchronizes the new command set; no data migration is needed.
