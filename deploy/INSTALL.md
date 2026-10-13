# DisCuss installation scaffold

This foundation archive is not a functional bot release. Native installers, locked voice/STT dependencies and configuration preflight must be completed and qualified before RELEASE_READY is enabled.

The planned runtime uses pinned uv-managed Python, one process, a system-level Linux systemd service or Windows AtStartup Scheduled Task, and protected JSON/state outside the release directory. Future updates must preserve state and support rollback.
