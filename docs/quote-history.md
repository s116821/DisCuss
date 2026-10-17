# Published quote lookup

`/discuss quotes member since until` searches the configured detection reporting channel for that person's published reports. `member` is required. The optional ISO date/time range defaults to the past seven days; `until` is exclusive. Dates without an offset use the configured leaderboard timezone; clock-change times require an explicit offset.

Only the primary bot's report messages count. New reports link the visible speaker name to their account, so changing a nickname does not lose attribution. Old plain-name reports are included only when the current name matches and retained minimal detection events identify exactly that person in the displayed minute. Ambiguous, deleted, malformed or unattributable history is skipped.

The command reads at most 2,000 recent messages for a range of at most 366 days and returns at most 20 quotes, with links to the original messages. Narrow the range if the search limit is reached. Delayed posts up to an hour after the requested endpoint are scanned, then filtered by the detection time inside the report. The displayed timestamp has minute precision. Historical timezone changes can make old reports unavailable.

Both the requester and bot need **View Channel** and **Read Message History** in the detection channel. Responses are private to the requester. No quotes are copied into SQLite, log files or backups, and deleted Discord posts cannot be restored from local statistics. No privileged Message Content intent is required for the bot's own messages.
