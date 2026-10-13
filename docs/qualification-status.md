# Roadmap implementation and qualification

October13,2026. All41 DEG issues were retrieved from the DegenerateDevs DisCuss roadmap before implementation. Issues with code are In Review, not Done; PRs remain stacked and unmerged. GitHub writes/commits use s116821 with its GitHub noreply identity, scoped process credentials and the workstation PowerShell identity hook. No shared account switch/global Git config change occurred.

| Work | Review |
| --- | --- |
| DEG-1 application foundation | [DisCuss#1](https://github.com/s116821/DisCuss/pull/1) |
| DEG-2 library foundation | [DiscordVoiceReception#1](https://github.com/s116821/DiscordVoiceReception/pull/1) |
| DEG-3/7–10 attributed transport/receiver | [DiscordVoiceReception#2](https://github.com/s116821/DiscordVoiceReception/pull/2) |
| DEG-4/6/14/21–25/27–31/33–34 protected policy/statistics/reporting | [DisCuss#2](https://github.com/s116821/DisCuss/pull/2) |
| DEG-13/15–20/32 one-process runtime and commands | [DisCuss#3](https://github.com/s116821/DisCuss/pull/3) |
| DEG-35–39 native deployment/recovery/distribution | [DisCuss#4](https://github.com/s116821/DisCuss/pull/4) |
| DEG-5 guarded live fixture tooling | [DiscordVoiceReception#3](https://github.com/s116821/DiscordVoiceReception/pull/3) |
| DEG-26 partial synthetic measurements | [DisCuss#5](https://github.com/s116821/DisCuss/pull/5) |

Both OSes passed quality, exact extracted install/setup exit/startup-definition/rerun/failed-candidate/two sequential upgrades/rollback/removal and real CPU synthetic speech evaluation. Results document significant recognition misses and bounded overload; passing evaluation means measurement completed, not acceptable recognition accuracy. Native tests ran on disposable hosted CI machines, never registered services/tasks on the shared workstation and never logged in to Discord.

## Outstanding external acceptance

DEG-11 and40 require actual DAVE/PCM/speaker/move/rekey/reconnect plus full application acceptance in an authorized temporary server, with protected dedicated bot configuration. The receiver harness discovers participants automatically without member IDs; solo phases do not establish multiple-speaker coverage. No such config was supplied; the available browser redirects to Discord login. The guarded harness is ready, but no real/production server or third-party audio was tested. Current native install tests do not satisfy genuine logged-off Linux/Windows VM reboot acceptance (DEG-35/36); no Hyper-V, VirtualBox, QEMU or VMware CLI lab is available here. Do not reboot this shared workstation to substitute for an isolated VM test.

DEG-12 requires owner PyPI name/publisher registration and live-qualified independent library publication. The application still uses an immutable development receiver source, not a stable PyPI pin. DEG-38's final stable dependency and DEG-41's public v1.0.0 release remain blocked on those prerequisites and DEG-40 acceptance. RELEASE_READY/PYPI_PUBLISH_READY are unset, and application preflight rejects the development source before tagging. There is no fabricated release version or custom commit classifier.

DEG-26 has only artificial US-English/short stress/burst CPU evidence. Accent/conversation/GPU/sustained-soak capacity and reliable counting need further qualification. A local decoder probe disabling compression fallback did not fix misses; adding keyword context produced overcounting (57 observed for20 expected), so that prompt was not adopted. Release notes must report these limits and qualified settings rather than treating the suite as perfect recognition.

OpenSpec proposal/design/spec/tasks/verification archives and synchronized canonical specs accompany each cohesive implementation PR. The full retrieved roadmap snapshot remains local to the task workspace; public docs summarize implementation and unresolved gates without publishing credentials or private voice data.
