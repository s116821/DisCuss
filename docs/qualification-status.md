# Roadmap implementation and qualification

October13,2026. All41 original DEG issues were retrieved from the DegenerateDevs DisCuss roadmap before implementation; DEG-42 adds contextual reporting and presentation refinements. The operator authorized bottom-up merging of the implementation stacks after temporary-server testing. Linked PRs and Linear issues record current merge/acceptance status. GitHub writes/commits use s116821 with its GitHub noreply identity, scoped process credentials and the workstation PowerShell identity hook. No shared account switch/global Git config change occurred.

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
| DEG-42 contextual alerts, readable named standings and explicit member word queries | [DisCuss#6](https://github.com/s116821/DisCuss/pull/6) |

Both OSes passed quality, exact extracted install/setup exit/startup-definition/rerun/failed-candidate/two sequential upgrades/rollback/removal and real CPU synthetic speech evaluation. Results document significant recognition misses and bounded overload; passing evaluation means measurement completed, not acceptable recognition accuracy. Native tests ran on disposable hosted CI machines, never registered services/tasks on the shared workstation and never logged in to Discord.

## Outstanding external acceptance

DEG-11 and40 require controlled DAVE/PCM/speaker/move/rekey/reconnect plus full application acceptance on both target OSes. A protected dedicated bot is now running in the operator's authorized temporary server on Windows; voice reception, local transcription and contextual detection reports were observed, with operator feedback driving the presentation changes. The receiver harness discovers participants automatically without member IDs; solo observation does not establish multiple-speaker/epoch/rekey/OS qualification. No community/production server was used. Current native install tests do not satisfy genuine logged-off Linux/Windows VM reboot acceptance (DEG-35/36); no Hyper-V, VirtualBox, QEMU or VMware CLI lab is available here. Do not reboot this shared workstation to substitute for an isolated VM test.

DiscordVoiceReception1.0.0 is published independently on PyPI and GitHub through trusted OIDC publishing; its wheel/sdist hashes match both registries. DisCuss now pins that exact PyPI version with hashed locked artifacts, completing DEG-12's consumer integration and DEG-38's stable dependency. Both projects' v1.0.0 GitHub releases are published with checksums/provenance, and the temporary bot runs the published application package. Development releases run automatically after successful main CI; immutable source dependencies remain supported when needed. DEG-41's comprehensive acceptance evidence remains separate from development publication; there are no readiness switches or qualification publication gates. There is no fabricated release version or custom commit classifier.

DEG-26 has only artificial US-English/short stress/burst CPU evidence. Accent/conversation/GPU/sustained-soak capacity and reliable counting need further qualification. A local decoder probe disabling compression fallback did not fix misses; adding keyword context produced overcounting (57 observed for20 expected), so that prompt was not adopted. Release notes must report these limits and qualified settings rather than treating the suite as perfect recognition.

OpenSpec proposal/design/spec/tasks/verification archives and synchronized canonical specs accompany each cohesive implementation PR. The full retrieved roadmap snapshot remains local to the task workspace; public docs summarize implementation and unresolved gates without publishing credentials or private voice data.
