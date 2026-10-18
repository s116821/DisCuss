# Statistics and reporting core

SQLite stores normalized detections and UTC timestamps, channel/member IDs, chunk replay identities, monitored intervals/checkpoints, opt-out preferences, report cursors and delivery receipts. There are no audio, full transcript or token columns. Store.ingest accepts attributed speech only; no typed-message ingestion adapter exists. A chunk is committed once even if retries use a changed dictionary.

The listener adapter must checkpoint actual healthy channel occupancy. Joining/leaving/moving, receiver failure or pause closes intervals; silence counts while capture is available. Duration queries union overlapping listeners per member and clip to half-open report windows. Restart recovery closes leases at their last durable checkpoint; it never adds downtime. Short uncheckpointed tails can be lost on abrupt crashes.

Total standings include all detections in the chosen calendar window. Scaled standings divide that same count by actual monitored hours in that window. The default 1800-second eligibility threshold applies only to scaled standings. Qualified monitored members with zero detections can have a zero rate; zero-duration members cannot. Reports have separate total/rate sections, recognizable member names and local calendar dates, without per-word breakdowns or numeric identity labels. Only `/discuss words member:<select a person>` provides per-word counts for that selected member. Names are escaped and pages stay below 1900 UTF16 units.

Scheduled snapshots reserve internal member-name slots and resolve names when delivered, preserving stable page receipts without storing display names. Cached members/users and bounded REST lookup provide account names; missing/deleted profiles use Unknown member. Earlier queued reports strip word rows and resolve ID labels before publication, shortening unusually long names if needed to retain their original page boundaries. Offline CLI standings use neutral names because the CLI does not connect to Discord.

Scheduling is independent of listener activity. It catches up closed windows from a durable cursor, queues a unique snapshot per server/cadence/window and advances cursors in one transaction. Shared boundaries have deterministic cadence evaluation and period/page identities. Disabled cadence cursors advance to the current window; changing toggles does not reconstruct data already retired. Very long downtime is caught up in bounded batches.

Delivery preserves acknowledged page receipts across retry/restart and serializes concurrent delivery for each server. A sender returns its Discord message ID; pages with receipts are skipped. If Discord accepts a message but its acknowledgement is lost, a retry may duplicate it. This at-least-once external ambiguity is explicit; no false exactly-once guarantee. Delivered snapshot text/member lists are discarded while minimal receipts remain until retirement.

Retention uses the largest enabled calendar period and preserves the tail needed by shorter open windows. For example, a week spanning December/January retains its December events and exposure after the yearly boundary. Pending unacknowledged old reports block retirement. Once all cadences are off, the explicit rolling-day policy applies.

Operator-only local operations (these require protected host/config access, not just a Discord account):

```sh
discuss --config /protected/config.json standings --server SERVER_ID --period week
discuss --config /protected/config.json backup /protected/new-backup.sqlite3
discuss --config /protected/config.json delete-member --server SERVER_ID --member MEMBER_ID
```

Delete removes that member's local detections, replay metadata, exposure and preferences; affected queued report snapshots are discarded. Already posted Discord messages require operator removal. Backups use SQLite's consistent backup API and never overwrite an existing destination. Restoring a backup is an explicit operator action with the application stopped.

The [application runtime](runtime.md) connects Discord voice reception, local transcription and reporting, and the [native installers](https://github.com/s116821/DisCuss/blob/main/deploy/INSTALL.md) provide boot startup. Personal opt-out/in preserves collected statistics and posted reports; no member-facing deletion command is registered. Operator maintenance and normal retention still apply. Broader live/reboot qualification remains separate from these implemented paths.
