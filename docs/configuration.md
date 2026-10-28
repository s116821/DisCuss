# Protected local configuration

Copy config.example.json into a protected machine-local config.json outside the release directory. Replace the example server/channel IDs and primary bot token with your own application setup, post the configured visible listening notice, then set privacy.notice_acknowledged=true. The checked-in example intentionally fails setup validation until completed. Never paste private tokens into chat, issues or command-line arguments.

Run `discuss --config /protected/path/config.json doctor` (Windows accepts an absolute NTFS path). This validates local schema and permissions without connecting to Discord. Missing/incomplete setup returns exit 2 with secret-safe field paths. Unknown schema versions fail intentionally; current schema_version is 1. JSON schema is config.schema.json and can be regenerated with `discuss schema --output config.schema.json`.

Use server terminology in all operator interfaces. bots declares each identity/token once; servers references names. Names and enabled tokens must be unique. One bot identity may be reused across separate servers. IDs are positive decimal strings, bounded to Discord's identifier range.

Linux config requires 0600 permissions. Windows preflight rejects broad Everyone/Authenticated Users/Users read grants; restrict NTFS access to the runtime identity, SYSTEM and administrators. The [native installers](https://github.com/s116821/DisCuss/blob/main/scripts/deploy/INSTALL.md) establish deployment ACLs and boot startup. State paths resolve relative to the config document; production state should be external, e.g. /var/lib/discuss or ProgramData/DisCuss/state.

## Policy defaults

Top-level `logging.level` defaults to `"INFO"`; choose `"WARNING"` or `"ERROR"` for quieter diagnostics. INFO includes all three supported levels. See [native service logs and queries](logging.md).

Head Hunt uses one primary_bot and an explicit voice_channels list by default. To roam all accessible ordinary voice channels, set head_hunt.all_channels=true and voice_channels=[]; newly created/removed channels take effect at the next evaluation without editing IDs. Optional head_hunt.excluded_channel_ids subtracts channels from either scope. One bot listens in one selected channel at a time. Evaluation interval defaults to600seconds. Ordered priority_member_ids interpolate maximum_weight=10 to minimum_weight=1; unlisted humans use default_weight=1. One priority member gets maximum; zero total affinity idles. Bots, excluded/unavailable members and forbidden/full/empty channels contribute no score.

Fixed Channels uses mode=fixed_channels and assignments with bot/channel_id. Each bot and channel appears once per server; the primary bot is assigned too. Separately create and authorize secondary applications and declare distinct enabled credentials before referencing them. The coordinator reconciles one or several listeners in the same process.

profanity.use_builtin_list=true by default. custom_words=[] appends normalized entries even with the built-in toggle off. NFKC/case folding and word/phrase boundaries apply. Longest matching phrase wins at a position; nested entries are not double-counted. Toggling the dictionary affects new detections, not committed chunks/history. The packaged Base85/zlib asset is repository search hygiene, not secrecy. Maintainers can use `uv run python scripts/encode_lexicon.py PRIVATE_INPUT src/discuss/assets/lexicon.json`; never commit the plaintext input.

leaderboards defaults: timezone UTC, ISO Monday weeks, sort_order=descending; reports.day=false and week/month/year=true; scaled.enabled=true and minimum_monitored_seconds=1800 per member per selected period. Ascending reverses metric ordering with stable numeric member-ID ties. Empty reports are suppressed by default; empty day reports always are. When all reports are disabled, retention_days_when_reports_disabled=30 applies; configurable 1–366 days.

Monitoring requires privacy.notice_acknowledged. monitoring_enabled=false disables assignments; privacy.excluded_member_ids excludes future processing. Runtime opt-out preferences have the same ingestion/exposure effect. Silence counts while genuinely monitored; server-muted/unavailable transmitters are excluded, rather than equating exposure with VAD speaking time.

## Replay and separate scheduled reports

`servers[].playback` defaults to disabled, `interval_seconds: 900`, `mode: "random"`, `max_clip_seconds: 8`, `context_seconds: 1.5`. See [replay lifecycle](playback.md) before enabling. No additional token or bot identity is required.

Mode `random` selects one weighted speaker and randomizes listening/replay timing; `cadence` selects one weighted speaker and replays at the cycle boundary. Set `mode: "first_curse"` to use random timing while accepting the first qualifying detection processed from any currently monitored eligible speaker. It preserves one clip per server and the winning listener/channel. Both randomized modes require `interval_seconds >= 120`; shorter values fail validation without changing modes. Explicit cadence supports intervals from five seconds. Existing shorter randomized configurations must be updated before upgrading.

`servers[].leaderboards.report_channel_id` is an optional destination for scheduled end-of-period leaderboards; null uses `servers[].report_channel_id`. This does not reroute detection reports or private commands. `detection_reporting.channel_id` remains its independent optional override. All destinations need View Channel and Send Messages. Quote lookup additionally needs Read Message History for bot and requester.

### Separate quotes and leaderboards

Merge these fields into a completed server entry, preserving its other nested settings. The IDs below are illustrative; replace them with your own server's text-channel IDs. Here `223456789012345678` is the leaderboard/notice channel and `323456789012345678` is the quotes channel. Setting a detection override does not move scheduled leaderboards. `/discuss quotes` reads the detection destination; it does not create a separate history destination.

```json
{
  "report_channel_id": "223456789012345678",
  "leaderboards": {"report_channel_id": null},
  "detection_reporting": {
    "enabled": true,
    "channel_id": "323456789012345678"
  },
  "playback": {"enabled": true, "interval_seconds": 600},
  "privacy": {
    "notice_acknowledged": true,
    "context_reporting_acknowledged": true
  }
}
```

This example deliberately chooses a **10-minute** playback cycle. The shipped default remains disabled with a **15-minute** (`900` seconds) interval; `600` is an operator override, not a changed product default. The playback interval is independent of `head_hunt.interval_seconds` and `detection_reporting.interval_seconds`. For playback, configure Speak in the [Developer Portal installation settings and actual voice-channel permissions](discord-setup.md).

## Editing a running installation

Keep credentials in the protected config, outside versioned code. Prepare a candidate in the same protected directory, preserve its private ownership/ACLs, and run `discuss --config CANDIDATE_PATH doctor` with the installed runtime. This is a local preflight; it does not verify Discord channel access. Check access separately before switching destinations. Replace the active config atomically so the watcher never reads a half-written document, retaining a protected rollback copy. Windows edits under `ProgramData` require elevation/UAC; do not grant broad file access as a workaround.

The watcher picks up policy changes in the same process. It releases/reconciles voice assignments and clears pending excerpts and captured replay clips on reload; no queued content is rerouted to a new destination. Expect a brief voice reconnect and an updated processing notice. Verify fresh runtime health, intended channels and permissions after the change. Changes to identities, tokens, transcription settings or state location require a restart. Invalid edits cause an intentional setup exit rather than silently retaining the prior policy; keep a valid backup for recovery. A newly published code release is applied through the verified installer, not by a config edit.
