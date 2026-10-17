# Native DisCuss operations

Self-hosted only. Download the Windows x64 ZIP or Linux x64 tar.gz plus SHA256SUMS from the same [GitHub Release](https://github.com/s116821/DisCuss/releases). Verify the archive checksum and [GitHub artifact attestation](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/verifying-the-provenance-of-binaries) before extraction. For example `sha256sum --check SHA256SUMS --ignore-missing`, or Windows `Get-FileHash .\DisCuss-vVERSION-windows-x64.zip -Algorithm SHA256` and compare with the downloaded checksum. Development releases install normally; the manifest records the exact receiver dependency. See qualification-status.md for live/reboot acceptance evidence.

Archives include no tokens, models, Node tooling or development checkout. The manifest is generated from the tag, includes every payload hash and pins uv0.13.0 and managed CPython3.12.15. Installers verify bundle contents and the bootstrap uv archive. Initial install needs Internet access to GitHub/PyPI/Astral for runtime dependencies. Linux requires x64 glibc and systemd; Windows requires x64 Windows with Task Scheduler and NTFS. No manual Python installation or Docker is needed. The conservative CPU speech setting uses two threads; see runtime.md for measured limitations.

## Linux

Install OS prerequisites (`curl`, `tar`, `ca-certificates`, `libopus0`; e.g. `sudo apt-get update && sudo apt-get install -y curl ca-certificates libopus0`). Extract the Linux archive and inspect `bash install.sh --plan`, then `sudo bash install.sh`. Default root is /opt/discuss: releases/VERSION contains isolated code; config.json and state/ remain outside versioned releases. A dedicated no-login discuss identity reads private config and owns state. Root owns runtime code and backups. The system-level discuss.service is enabled at boot, independent of user login, waits for network-online, restarts failures at most three times per five-minute burst and stops intentional setup exits without retry.

The installed placeholder config causes an intentional setup message, so no bot connects. Edit /opt/discuss/config.json locally using sudo, keep its mode0600 and owner discuss. Read configuration.md/runtime.md before setting tokens, decimal server/channel IDs, primary identity and privacy acknowledgement. Do not send tokens to support or commit them. The installer requires state_dir to resolve to /opt/discuss/state (or ROOT/state for --root).

```sh
PY=$(sudo python3 -c 'import json; print(json.load(open("/opt/discuss/current.json"))["python"])')
sudo -u discuss "$PY" -m discuss.cli --config /opt/discuss/config.json model-setup
sudo -u discuss "$PY" -m discuss.cli --config /opt/discuss/config.json doctor --runtime
sudo systemctl start discuss.service
sudo systemctl status discuss.service
sudo journalctl -u discuss.service -n 100 --no-pager
sudo -u discuss "$PY" -m discuss.cli status --state-dir /opt/discuss/state
sudo systemctl stop discuss.service
sudo systemctl disable discuss.service
```

The example PY lookup uses a convenient existing python3 only for reading metadata; installation itself needs no system Python. Without it read the interpreter path from current.json using sudo. Boot executes that fixed interpreter directly. Healthy status requires fresh runtime snapshots, intended channel, receiver/DAVE readiness and speech admission; a running systemd unit alone is insufficient.

## Windows

Extract to a local folder. In elevated Windows PowerShell, inspect ` .\install.ps1 -Plan`, then run ` .\install.ps1`. Default root is C:\ProgramData\DisCuss. The installer creates a single DisCuss Task Scheduler task with AtStartup, LocalService (SID S-1-5-19) ServiceAccount logon, Limited privileges, unlimited execution time, IgnoreNew overlap policy, network availability, battery allowance and three one-minute failure retries. It runs while users are logged off; no stored user password or interactive window is needed. LocalService has anonymous outbound OS network credentials; Discord uses the bot's HTTPS authorization. Proxy/firewall/domain environments may require operator network setup.

NTFS ACLs give LocalService code read/execute, config read, state modify; Administrators/SYSTEM retain control, recovery snapshots remain admin-only. Keep config and state outside versioned code. The task initially exits intentionally with setup guidance in state\runtime.log. Edit protected config locally as administrator; tokens stay in this file, not task arguments. Changing enabled identities/tokens/model settings requires restarting the task. Do not weaken ACLs to fix setup errors.

```powershell
$root = 'C:\ProgramData\DisCuss'
$python = (Get-Content -LiteralPath "$root\current.json" -Raw | ConvertFrom-Json).python
& $python -m discuss.cli --config "$root\config.json" model-setup
& $python -m discuss.cli --config "$root\config.json" doctor --runtime
Start-ScheduledTask -TaskName DisCuss
Get-ScheduledTask -TaskName DisCuss
Get-ScheduledTaskInfo -TaskName DisCuss
Get-Content -LiteralPath "$root\state\runtime.log" -Tail 100
& $python -m discuss.cli status --state-dir "$root\state"
Stop-ScheduledTask -TaskName DisCuss
Disable-ScheduledTask -TaskName DisCuss
```

Model setup is explicit and can run before tokens using `model-setup --state-dir "$root\state"`. Running it elevated gives files the state's inherited private runtime permissions. Task Scheduler stop can terminate the Python process; crash recovery uses durable exposure checkpoints and never counts downtime. Linux SIGTERM allows graceful cleanup. Configure host log rotation; the Windows diagnostic file is append-only.

## Backups, updates and rollback

Before an update inspect status/logs, stop the runtime, and retain a protected external backup. Use the active interpreter with `-m discuss.cli --config PATH backup DESTINATION.sqlite3` for a consistent SQLite snapshot; protect backups to the same privacy standard as live state. Never copy only the live .sqlite3 file while WAL is active. Config contains secrets, so copy it only to a protected location. A model cache can be copied separately while stopped. Published Discord messages and external backups need manual cleanup after deletion requests.

Install the next verified archive using the same root/task name. The installer rejects unrelated startup registrations and same-version manifests that differ. It stops the old runtime, backs up its startup definition/config/SQLite (read-only backup API, no old-state migrations), prepares the isolated candidate and checks imports/native decoding before switching the startup interpreter. Models, opt-out preferences/history and protected config remain in place. A failed candidate restores the prior startup registration and restarts it if previously running. Review model/config compatibility notes and run doctor --runtime before normal operation.

Explicit rollback restores the snapshot captured immediately before the last version switch, so data collected after that snapshot is not part of the restored history. A fresh recovery snapshot of current state is retained first. Use `sudo bash install.sh --operation rollback` or ` .\install.ps1 -Operation Rollback` from an extracted trusted archive. Config and database are restored through safe backup APIs, with the previous interpreter selected. Model caches remain; the prior pinned revision must still exist. Keep backups until compatibility is verified. SQLite migrations have dedicated offline preservation tests; actual post-upgrade live collection remains a qualification step.

Rerunning the same verified archive preserves config/state and does not replace the previous-version rollback point. There is no automatic pruning of recovery snapshots or old releases. Removal is `sudo bash install.sh --operation uninstall` or ` .\install.ps1 -Operation Uninstall`: only startup is unregistered. Config, SQLite, models, logs, releases and backups remain. Explicit permanent data removal is an operator decision after backups/deletion obligations; the installer never recursively deletes these paths.

## Troubleshooting and qualification

Use doctor for schema/private ACL errors; use doctor --runtime for missing model/native dependencies. Tokens and exception input are redacted. A revoked token stops intentionally; resolve authorization then start again. Missing primary report permissions prevent the notice and listening. Receiver not ready, queue pressure or identity disconnect closes monitored exposure. Reports remain durable for retry; lost external acknowledgements have documented at-least-once ambiguity. See statistics.md for calendar/retention and privacy.md for notice/opt-out/deletion.

Tests must use local synthetic fixtures or an explicitly authorized disposable Discord server. CI privileged install tests run only on disposable GitHub-hosted OS runners and never log in to Discord. They check exact extracted assets, setup exits, startup definitions, rerun, state preservation, upgrade/rollback and removal. These do not demonstrate actual machine reboot or live DAVE behavior. Development releases run automatically after successful CI. Record actual Linux/Windows logged-off reboot and disposable-server acceptance evidence separately; these checks do not claim that evidence.

References: [uv managed Python](https://docs.astral.sh/uv/guides/install-python/), [Task Scheduler LocalService principal](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal), [systemd service supervision](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html). Contributor workflow and Conventional Commit/OpenSpec requirements are in the repository AGENTS.md and README.

## Recognizing the Windows process

New installations/upgrades launch `DisCuss-Service.exe` in the versioned private virtual environment. This is a copy of the real managed interpreter and its adjacent runtime DLLs, not a wrapper spawning Python children. The existing `discuss.exe` CLI is preserved. Task Manager Details shows this dedicated image; its underlying signed Python file metadata and grouping in other Task Manager views are controlled by Windows, so an Apps-style parent/child group is not promised. Other projects and the shared Python installation are unchanged. Upgrades/rollback continue to use the recorded executable path.
