# Running DisCuss

The application owns one Python process, a shared SQLite store, one local Whisper model and a single bounded inference thread. Each separately authorized bot identity owns its own gateway/voice connections. One identity can join one channel per server, with independent assignments across servers. Fixed mode needs distinct bot applications for simultaneous channels within the same server. Do not use user tokens.

Development requires `uv sync --locked --all-groups --extra runtime`. Linux additionally needs the distribution's `libopus0` package. The runtime pins `discord-voice-reception==1.0.0` from PyPI with hashed locked distributions. Its receiver source is identical to the previously used immutable development commit. discord.py 2.7.1 handles gateway/DAVE sessions; the receiver handles attributed bounded audio delivery. See qualification-status.md for live MLS/DAVE acceptance evidence.

## Protected setup

Copy config.example.json outside the checkout, restrict it to the operator/service account, replace placeholder bot tokens, add decimal server/channel IDs and explicitly acknowledge the visible processing notice. On Linux use mode 0600. Windows requires private NTFS ACLs (no broad Users, Authenticated Users or Everyone read access). State paths are relative to the config's directory unless absolute. Keep state/model cache outside versioned code.

Use the Discord Developer Portal to create legitimate bot applications and invite each to the intended server using `bot` and `applications.commands` scopes. Grant View Channel and Connect in selected voice channels; grant View Channel/Send Messages for the primary bot's report channel. Administrator privileges are unnecessary. Message-content/member privileged intents are not required. Configure primary_bot explicitly: only that identity registers server-scoped `/discuss` commands, publishes the notice and delivers reports. An unavailable primary notice channel prevents listening.

```sh
uv run --extra runtime discuss --config /protected/config.json doctor
uv run --extra runtime discuss --config /protected/config.json model-setup
uv run --extra runtime discuss --config /protected/config.json doctor --runtime
uv run --extra runtime discuss --config /protected/config.json run
uv run --extra runtime discuss status --state-dir /protected/state
```

`model-setup --state-dir PATH` also works before credentials are supplied. It explicitly downloads a pinned Systran/faster-whisper-small revision, checks required files and records SHA-256 hashes. Normal startup never downloads models or sends speech to a cloud service. CPU int8/two threads is the conservative default; CUDA setup is operator-managed. Model cache is not bundled in application archives.

Setup failures stop with an intentional success exit for service supervision; `doctor` gives exit 2. This prevents missing credentials/model/permissions from creating restart loops. Transient runtime failures use exit 1. Runtime status includes snapshot age: a snapshot older than 30 seconds is stale, even if it last said running. Logs contain generic setup/health failures, never tokens, PCM or transcripts. Optional `--log-file PATH` must appear before the subcommand and have private ACLs. Operators should rotate logs; snapshots alone do not prove live audio capture.

## Listening and speech

Head Hunt draws once every configured interval (default 600 seconds). It sums eligible human affinities by channel and uses weighted roulette; ordered preferred members interpolate from maximum to minimum affinity, all others use the default. Bots, opted-out/excluded members and inaccessible/full/empty channels are ineligible. Zero eligible weight idles. Membership updates checkpoint exposure but do not trigger a new draw. A repeat winner keeps its connection. Fixed mode uses the same coordinator, health, speech and report path.

Policy changes reload in the same process; changing identities, tokens, model settings or state directory requires a restart. Invalid edits stop safely and leave a generic diagnostic. Admin disable is durable across restart and cannot override config/privacy restrictions. Gateway/voice failures retry independently; one server or identity does not hold another's voice handshake. Report timers continue while a voice handshake awaits completion.

PCM and transcripts exist only in memory. Each member/channel has an amplitude VAD buffer with silence/max-duration limits. RTP gaps insert bounded silence to preserve word offsets, handoffs split buffers, concealed packets cannot begin speech, and inference/admission buffers have caps. The queue drops overload rather than growing unbounded. STT is imperfect; noise, names, accents and hallucinations can produce false counts. Exposure closes when receive/inference admission is unhealthy; silence while healthy counts. Word offsets select calendar windows, and pending inference fences report snapshots to avoid silently losing midnight words. Shutdown waits for an active native inference thread and releases identities/state; no inference subprocesses are launched.

## Commands and privacy

`/discuss standings` selects day/week/month/year (week default) and shows total/rate summaries. `/discuss words` requires selecting a member by name and is the only per-word breakdown. Replies are ephemeral, paginated, and disable mentions. Member/channel/server/bot names identify Discord output; missing entities use neutral labels. `opt_out` stops only your future collection and discards queued/active buffers. `opt_in` clears your preference subject to server policy. `delete_self` removes your local statistics and retains only an opt-out preference. An administrator can use `monitoring` and `status`; unauthorized requests cannot alter monitoring. Previously published messages and external backups need operator cleanup. See privacy.md and statistics.md for retention, reporting ambiguity and deletion limits.

## Evidence and limits

The neutral synthetic Windows CPU fixture in benchmarks/windows-synthetic-2026-10-13.json contains no user audio/transcript. With two CPU threads it transcribed 6.03 seconds in 2.80–3.29 seconds, about 650 MiB peak RSS, one process and no child inference processes. A real local backend run through segmentation/storage produced two custom phrase detections across three chunks with zero drops/failures. This is one reproducible offline fixture, not an accent/capacity or Discord acceptance claim. Generate your own benchmark with `uv run --extra runtime python scripts/benchmark_speech.py --help`; never record other members to build fixtures.

Official references: [discord.py voice API](https://discordpy.readthedocs.io/en/stable/api.html#voice), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [pinned model](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120), [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy). Operators are responsible for permission/notice compliance and authorized server deployment.

## Diagnosing delayed reports

`/discuss status` and the metadata-only `state/health.json` show speech queue depth, oldest capture age and last inference duration, plus replay counts/failures. Capture handles heard members in parallel; local recognition intentionally uses one bounded worker and queue. Slow CPU inference, a busy queue and the configured detection reporting interval can delay reports. The ordinary immediate feed does not add a minute-long timer. A high oldest-capture age alongside long inference time indicates recognition backlog; do not diagnose it as a dictionary miss. No audio/transcripts are included in diagnostics.
