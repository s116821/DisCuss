# Design

## Context

The CLI currently redirects stdout/stderr for Windows, while Client.start does not configure logging and important recovery paths catch exceptions silently. Linux already uses systemd; Windows runs a protected LOCAL SERVICE scheduled task. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** one logging policy with native severity, reliable fallback, useful reconnect evidence and bounded content-safe storage.

**Non-Goals:** recording speech/transcripts, enabling DEBUG, replacing Task Scheduler with a Windows service wrapper, changing monitoring decisions or creating new one-off operator scripts.

## Decisions

- Use stdlib logging, one INFO/WARNING/ERROR config field and structured JSON events. This avoids a new logging dependency and supports the same instrumentation on both OSes.
- Stream events to stderr; systemd explicitly captures stdout/stderr and parses priority prefixes. On Windows use the native ReportEvent API through ctypes; install registers the Application source with the OS EventLog API. A protected rotating runtime.log (5 MiB plus three backups) is always available, with the existing CLI override retained.
- Instrument application lifecycle, per-minute aggregate health, voice ready/disconnect/resume/state, requested joins/releases and assignment/retry reasons, playback outcomes and speech/report failures. Emit changed-state/failure events at attempt boundaries to avoid timer flooding.
- Format controlled application event names and allowlisted bounded metadata. Never persist arbitrary library bodies or exception messages; retain exception class, integer status/code/errno and stack locations without source text/locals. Suppress external INFO chatter and retain warnings/errors as metadata-only summaries.
- Native sink errors disable that sink after one fallback warning. Other handlers continue; setup/log-file failures remain intentional actionable setup failures.
- Keep configuration edits/restarts as ordinary elevated PowerShell commands and the supported installer. No additional local helper files are needed for deployment.
- User steering adds a 120-second minimum to both randomized modes. Validate the minimum in the model and conditional JSON schema rather than coercing modes; cadence remains explicitly available from five seconds. This replaces earlier short-interval fallback behavior.

## Risks / Trade-offs

- Native Event Log requires prior registration → perform idempotent source registration in the elevated installer and verify actual OS event delivery in Windows native validation.
- Summarized external messages lose some text → controlled application events plus exception type/code/stack retain routing and recovery context without retaining speech/secrets.
- File rotation and Windows ACLs → inherit protected state-directory ACLs and validate existing files; test rotation bounds and secret exclusion.
- Fatal exit versus handled recovery → log top-level failures and asyncio exceptions as ERROR while retryable events use WARNING and normal lifecycle uses INFO.

## Migration Plan

Existing configs default to INFO. Upgrade using verified release installers, add logging.level=INFO to local protected config, retain first_curse/120-second playback and all unrelated settings, restart and verify fresh health plus real native/file startup events. Old versions require removing the new logging section before rollback. Historical empty logs cannot be reconstructed.
