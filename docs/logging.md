# Background service logs

DisCuss uses Python's standard logging API and the operating system's native log collector. Linux systemd captures events in the journal. Windows writes to **Event Viewer → Windows Logs → Application**, source **DisCuss**. Task Scheduler's Operational history records task starts/exits; the Application log records what the bot does inside that task.

Set the top-level protected configuration field:

```json
"logging": {"level": "INFO"}
```

The default is `INFO`. It includes INFO, WARNING and ERROR; `WARNING` includes WARNING and ERROR; `ERROR` includes only ERROR. Values must be uppercase. DEBUG is unavailable. Valid level changes apply during normal config reload; that existing reload also clears pending clips/excerpts and briefly reconciles voice assignments. Restart after a code upgrade.

## Reading logs

Linux:

```sh
sudo journalctl -u discuss.service -f -p info
sudo journalctl -u discuss.service --since '15 minutes ago' -p warning
```

Windows PowerShell:

```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='DisCuss'} -MaxEvents 50 |
    Select-Object TimeCreated, LevelDisplayName, Message
```

The elevated Windows installer registers the source idempotently. The bot still runs as LOCAL SERVICE; no administrator runtime or extra process is required. Registration remains for reading historical events after uninstall. Native collectors manage their own retention and read permissions. Event Log and journald are separate OS APIs, rather than identical storage backends.

Both platforms also retain structured JSON lines in the protected state directory's `runtime.log`. The existing `--log-file PATH` run option overrides that path. The file rotates at five MiB with three backups (`.1`–`.3`), retaining at most about twenty MiB. Windows files inherit the protected state-directory ACL; Linux files use private permissions. Native delivery failure disables that sink after one fallback warning and monitoring continues with file/console events. A writable private file path is required; file setup errors stop intentionally with setup guidance.

To follow the Windows file from an elevated shell:

```powershell
Get-Content -LiteralPath C:\ProgramData\DisCuss\state\runtime.log -Tail 50 -Wait
```

## Interpreting events

Every record has a UTC timestamp, severity, event identifier and process ID. `service_starting`, `service_ready`, `service_stopping` and `service_stopped` identify application lifecycle; `gateway_ready` and `voice_capture_ready` identify Discord readiness separately. A `health_summary` every minute records aggregate queue/processing/failure counts without speech content.

Forced termination (including stopping a Windows scheduled task) can omit shutdown events. A new PID alone does not prove a crash: correlate startup/error events with operator restarts and Task Scheduler history when that history is enabled. Playback cycle events also show randomized listening delays and cycles that ended without a qualifying clip.

For leave/rejoin investigations, compare `assignment_requested` / `assignment_released` reasons with `head_hunt_evaluated`, `voice_join_requested`, `voice_leave_requested`, `bot_voice_state_changed`, `gateway_disconnected` and `gateway_resumed`. A new PID and startup event indicate a new process. Voice events under one PID indicate an internal connection/assignment change. Head Hunt's evaluation interval is independent of playback timing.

Retryable assignment, connection and delivery failures use WARNING; unrecoverable startup/task/processing failures use ERROR. Recovery events return to INFO. Consecutive speech failures and unchanged reconciliation errors do not emit an event on every timer tick; periodic health still exposes cumulative counters. Native connection codes, exception class and stack locations help identify the failed component. External-library warnings/errors are summarized as `library_diagnostic`; their arbitrary message bodies and INFO chatter are omitted.

Tokens, raw audio, transcript excerpts and detected words are never diagnostic fields. Exception messages, source lines and local variables are excluded. Protected operational metadata can include routing identifiers, resolved channel/server names and configured bot aliases. Logs do not replace Discord quote history or retain speech for debugging.

Older releases could redirect stdout/stderr without configuring the logging API, leaving an empty file during normal operation. This change cannot reconstruct those missing historical events.

## Ordinary configuration edits and restarts

For boot failures, correlate `service_starting`, `gateway_connecting` and `gateway_connection_failed` with `gateway_ready`. Transient failures retry with a 30-second maximum backoff until recovery or shutdown; they do not exhaust a fixed attempt budget. `gateway_authorization_failed` / `gateway_setup_failed` require correcting permanent setup. Existing Windows Task Scheduler retries remain a bounded fallback for process crashes, not the network recovery mechanism. A historical result `0x1` means that run exited with code 1; it does not identify the cause without the service events.

Use an elevated PowerShell session for the existing Windows installation. Edit the protected JSON directly with your editor, preserving unrelated settings, then validate and restart using the installed interpreter:

```powershell
$root = 'C:\ProgramData\DisCuss'
$current = Get-Content -LiteralPath "$root\current.json" -Raw -Encoding UTF8 | ConvertFrom-Json
& $current.python -m discuss.cli --config "$root\config.json" doctor
if ($LASTEXITCODE -ne 0) { throw 'Fix configuration before restarting' }
Stop-ScheduledTask -TaskName DisCuss
while ((Get-ScheduledTask -TaskName DisCuss).State -eq 'Running') { Start-Sleep -Milliseconds 250 }
Start-ScheduledTask -TaskName DisCuss
```

For atomic edits, prepare/validate a private candidate beside the config and replace the file as described in [configuration](configuration.md#editing-a-running-installation). Keep a protected rollback copy. Linux uses `sudo systemctl restart discuss.service` after validation. These are ordinary administrative commands; no generated one-off script is required. Native code upgrades still use the verified release installer, preserving state/models and boot settings.
