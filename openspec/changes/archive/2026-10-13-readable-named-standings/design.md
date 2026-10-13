# Design
Render compact Discord Markdown sections for total cusses and cusses per monitored hour. Use local calendar dates instead of UTC ISO timestamp ranges. Names are escaped/truncated by UTF16 units; pages reserve bounded space per member label and retain section context after a split.

Scheduled snapshots contain padded internal member-name placeholders rather than persistent display names. The SDK resolves cached members/users and bounded REST lookups at delivery, then substitutes names within reserved limits. Old queued text loses per-word rows and resolves its legacy member labels, shrinking long names if needed while preserving page/receipt identities. Missing/deleted profiles use Unknown member, never IDs. Lookups are bounded and cache misses expire; failures do not expose exception text or stop counting.

The words command takes a required Discord Member parameter so the UI selects by name, and is the only public per-word breakdown. Status resolves server, channel and bot names; a disconnected listener says Not connected. Offline CLI uses neutral labels because it does not log in. No names/transcripts are added to event storage; snapshots remain immutable and per-member deletion still invalidates queued reports.

Name lookup has four concurrent slots, five-second request timeouts, a 4096-entry memory cache, 15-minute successes and one-minute unavailable-profile retries. Legacy page substitution makes one pass (so a real display name resembling an internal label cannot be interpreted again) and progressively shortens labels if needed, preserving the page receipt identity.

Keep the authorized temporary app running while implementing, then stop/restart it cleanly after verification. Remove the detection header without changing matching/grouping/counting. Finish/archive/sync in this PR before the authorized bottom-up stack merge.
