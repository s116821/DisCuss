# Sampled voice replays

Replay is optional and disabled in shipped configuration. Set `servers[].playback.enabled` to `true` to use the defaults: a 900-second cycle, randomized listening/playback timing, at most eight seconds of audio and 1.5 seconds of context around a recognized curse.

For a ten-minute cycle, set `servers[].playback.interval_seconds` to `600`; the shipped default remains `900`. This setting is independent of the Head Hunt channel-evaluation interval and text-report batching interval. See the [combined channel/playback example](configuration.md#separate-quotes-and-leaderboards) and [policy reload guidance](configuration.md#editing-a-running-installation).

Choose a mode with `servers[].playback.mode`:

| Mode | Who supplies the clip | Listening and replay timing |
| --- | --- | --- |
| `random` (default) | One eligible person sampled using Head Hunt member weights | Random listening start; random replay after acquisition, within the remaining cycle |
| `cadence` | One eligible person sampled using Head Hunt member weights | Listen from cycle start; replay at the cycle boundary |
| `first_curse` | First qualifying detection processed from any currently heard eligible person | Same randomized listening and post-acquisition replay timing as `random` |

For example, merge `"playback": {"enabled": true, "mode": "first_curse", "interval_seconds": 600}` into a completed server entry, preserving any other playback settings. First-curse mode does not preselect a speaker or use member weights. Before acquisition, eligibility follows the latest monitored assignments, including new arrivals. The first qualifying detection processed wins; recognition order can differ from the order people actually spoke. Later detections cannot replace the acquired clip. With multiple listeners, the winning listener replays in its original channel.

Weighted selection in `random` and `cadence` uses the existing Head Hunt priority list and maximum/minimum/default weights, including in Fixed Channels mode. Only after a qualifying clip is captured and available does randomized timing choose its replay time, leaving room for the clip's duration. Listening start does not schedule playback. No qualifying clip means a silent cycle. None of these modes records an unmonitored channel or moves independently of Head Hunt. One bot identity hears only its currently joined voice channel; first-curse mode does not add simultaneous coverage of other channels.

Intervals must be at least five seconds. Random intervals below 60 seconds automatically become cadence and emit a warning. First-curse intervals below 60 seconds also warn and use cadence timing, preserving all-speaker eligibility. Short cycles may be silent if recognition does not finish in time.

One pending short clip per server stays in memory only. It never becomes an audio file, SQLite content, a log entry or a backup. Before capture, opt-out/deletion/disable, exclusion/departure or a changed channel cancels a selected speaker; in first-curse mode that person loses eligibility while other eligible speakers remain available. Disabling monitoring/playback cancels uncaptured cycles. Once captured, a clip remains scheduled even if the person leaves or opts out. It only plays if the original listener is still connected to the original voice channel; it is never rerouted. Reload/shutdown discards RAM-only clips. Playback uses the existing in-process Discord encoder, without FFmpeg or another Python worker. Already transmitted voice cannot be recalled, and other Discord clients may record what they hear.

Request **Speak** under the Developer Portal's **Installation → Default Install Settings → Guild Install** bot permissions, and verify it is allowed by the installed role and current voice-channel overrides. Receiving voice can work while playback is blocked. Check mute/suppression state after permission changes and reconnect if needed; see [Discord setup and troubleshooting](discord-setup.md). The processing notice says captured clips may replay after opt-out. Missing permissions or unavailable playback skips the clip and appears in diagnostics. Recognition and quote boundaries remain approximate; clips are cut to the available recognized chunk rather than retaining a continuous conversation recording.
