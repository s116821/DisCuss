# Verification

51 offline tests pass on Windows, including native resampling, local-only loading, per-member VAD, timestamped midnight detections, bounded queue/buffers, thread cancellation, independent servers and report timers during a blocked handshake, primary command authorization/privacy and v1-to-v2 migration. Ruff, format, ty, actual semantic-release analyzer (13 cases), uv wheel/sdist build pass. CI now installs the runtime extra and Linux Opus and runs both OS matrices.

Native CPU benchmark: pinned small model, two CPU threads, neutral synthetic 6.03s clip, inference 2.80–3.29s, about650MiB peak RSS, one Python process/no inference subprocess. Full local segmented backend emitted three chunks/two custom phrase detections with zero drop/failure. Audio stays outside repository and neither benchmark artifact nor SQLite contains transcripts.

No bot login, production-server connection or real member audio was used. Live DAVE/attribution/privacy/report acceptance remains gated on a protected disposable-server configuration. Receiver archive dependency is development-only, awaiting qualified stable PyPI publication. Native installers and VM reboot evidence remain separate work; this archive claims offline runtime contracts only.
