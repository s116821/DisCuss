# Protected local configuration

Copy config.example.json into a protected machine-local config.json outside the release directory. Replace the example server/channel IDs and primary bot token with your own application setup, post the configured visible listening notice, then set privacy.notice_acknowledged=true. The checked-in example intentionally fails setup validation until completed. Never paste private tokens into chat, issues or command-line arguments.

Run `discuss --config /protected/path/config.json doctor` (Windows accepts an absolute NTFS path). This validates local schema and permissions without connecting to Discord. Missing/incomplete setup returns exit 2 with secret-safe field paths. Unknown schema versions fail intentionally; current schema_version is 1. JSON schema is config.schema.json and can be regenerated with `discuss schema --output config.schema.json`.

Use server terminology in all operator interfaces. bots declares each identity/token once; servers references names. Names and enabled tokens must be unique. One bot identity may be reused across separate servers. IDs are positive decimal strings, bounded to Discord's identifier range.

Linux config requires 0600 permissions. Windows preflight rejects broad Everyone/Authenticated Users/Users read grants; restrict NTFS access to the runtime identity, SYSTEM and administrators. Native installers will establish deployment ACLs; this core PR does not install a task/service. State paths resolve relative to the config document; production state should be external, e.g. /var/lib/discuss or ProgramData/DisCuss/state.

## Policy defaults

Head Hunt uses one primary_bot and voice_channels. Evaluation interval defaults to 600 seconds. Ordered priority_member_ids interpolate maximum_weight=10 to minimum_weight=1; unlisted humans use default_weight=1. One priority member gets maximum; zero total affinity idles. Bots, excluded/unavailable members and forbidden/full/empty channels contribute no score.

Fixed Channels uses mode=fixed_channels and assignments with bot/channel_id. Each bot and channel appears once per server; the primary bot is assigned too. Separately create and authorize secondary applications and declare distinct enabled credentials before referencing them. The same policy supports one or several listeners. Runtime reconciliation comes in the coordinator PR.

profanity.use_builtin_list=true by default. custom_words=[] appends normalized entries even with the built-in toggle off. NFKC/case folding and word/phrase boundaries apply. Longest matching phrase wins at a position; nested entries are not double-counted. Toggling the dictionary affects new detections, not committed chunks/history. The packaged Base85/zlib asset is repository search hygiene, not secrecy. Maintainers can use `uv run python scripts/encode_lexicon.py PRIVATE_INPUT src/discuss/assets/lexicon.json`; never commit the plaintext input.

leaderboards defaults: timezone UTC, ISO Monday weeks, sort_order=descending; reports.day=false and week/month/year=true; scaled.enabled=true and minimum_monitored_seconds=1800 per member per selected period. Ascending reverses metric ordering with stable numeric member-ID ties. Empty reports are suppressed by default; empty day reports always are. When all reports are disabled, retention_days_when_reports_disabled=30 applies; configurable 1–366 days.

Monitoring requires privacy.notice_acknowledged. monitoring_enabled=false disables assignments; privacy.excluded_member_ids excludes future processing. Runtime opt-out preferences have the same ingestion/exposure effect. Silence counts while genuinely monitored; server-muted/unavailable transmitters are excluded, rather than equating exposure with VAD speaking time.
