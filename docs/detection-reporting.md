# Contextual detection reports (DEG-42)

Detection reports are optional, disabled by default, and shared by every listener serving one server. The primary bot sends them to the leaderboard report_channel_id by default. Set detection_reporting.channel_id for a separate text channel. Each server retains its own destination, cadence and privacy policy within the single Python process.

Merge this fragment into an existing server entry (IDs are placeholders):

```json
{
  "report_channel_id": "223456789012345678",
  "detection_reporting": {
    "enabled": true,
    "channel_id": null,
    "context_words_per_side": 3,
    "interval_seconds": 0,
    "max_pending_instances": 1000,
    "max_pending_bytes": 1048576,
    "max_pending_age_seconds": 300,
    "max_pages_per_flush": 10
  },
  "privacy": {
    "notice_acknowledged": true,
    "context_reporting_acknowledged": true
  }
}
```

Enabling requires the separate context-publication acknowledgement. Tell participants beforehand that recognized excerpts will be posted to Discord and who can see the channel. The primary processing notice automatically discloses excerpt size, destination and Discord retention. An override must be a text channel in the same server; grant the primary bot View Channel/Send Messages there, without Administrator.

Three words per side means up to six surrounding words, seven including a one-word match. Word boundaries use the same normalization as the existing lexicon. Original recognized case/punctuation are preserved, and counted matches are highlighted. Overlapping contexts merge transitively for one speaker/chunk; different speakers/chunks remain separate instances. Context is clipped at completed speech chunk boundaries. Oversized groups split to fit messages; a split's repeated context can show an earlier match without highlighting/counting it again. Counts use the existing longest-phrase rule, with no new scoring algorithm.

Example with neutral custom tracked words:

> Stark (123) : “that **violet** word was **shade** today”, October 13, 2026 @ 5:26 pm CDT -> 2 cusses

Each line uses the group's earliest detection in the source server's configured leaderboard timezone. Names come from cached members, with member-ID fallback. Server/channel IDs remain internal routing metadata and do not appear at the end of alerts. This is recognized text and may be wrong; a report does not prove what someone actually said.

Interval 0 dispatches completed recognition without an additional batching delay. Nearby matches become one instance; multiple already pending instances can share a message. A positive interval (e.g. 60 seconds) starts with the first pending instance and combines that window into a multi-line digest. Empty windows send nothing. Digests paginate below 1900 UTF-16 units. Page budgets continue the same digest on later ticks rather than waiting another interval; new arrivals wait for their subsequent window. SDK rate limits can delay sends. Delivery runs independently of capture, counting and calendar reports, with mentions disabled, markup escaped and embeds suppressed.

## Memory, retry and cleanup

Quotes remain in memory only. SQLite keeps existing minimal detections/chunk IDs, with no excerpt columns; no snippets/audio enter logs or backups. Per-server instance/UTF8 byte/age caps apply, plus a combined 4096-instance/4 MiB process cap. Overflow evicts oldest pending feed items; very large/pathological text can be omitted. Default expiry is five minutes; configured age must cover the interval. Counts stay intact when delivery drops/expires/fails.

Acknowledged pages leave memory and are not resent on normal retry. Failed pages retry after ten seconds, subject to expiry/privacy. A lost Discord acknowledgement can cause a duplicate if the provider already accepted the message. There is no persistent excerpt outbox or restart catch-up: restarting/shutting down discards pending quotes. Configuration/destination changes clear queued excerpts instead of moving them elsewhere.

Opt-outs, exclusions, monitoring disable and deletion suppress applicable pending excerpts. In-flight sends are cancelled where possible, but already accepted Discord text cannot be recalled by queue cleanup. CLI deletion removes backing chunk metadata, suppressing its queued quotes at the next check. Statistics retirement can remove backing chunks too. Already posted quotes follow Discord/channel retention and require operator removal after deletion requests; the service does not silently erase prior Discord messages.

Use /discuss status or the local status snapshot for pending counts/bytes, drops/expiry and delivery failures; diagnostics contain no quote bodies. Missing destination permissions, disconnects and retries do not stop ordinary statistics/leaderboards. Verification uses offline synthetic fixtures; actual Discord output remains unqualified until the authorized temporary test setup is ready.
