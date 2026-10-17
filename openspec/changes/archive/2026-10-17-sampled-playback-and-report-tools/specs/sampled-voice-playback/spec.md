## Purpose
Replay occasional attributed curse clips for entertainment while keeping audio bounded, ephemeral and subject to personal participation controls.

## ADDED Requirements

### Requirement: Weighted randomized replay cycle
Playback SHALL be disabled by default and use a 900-second default interval. Each enabled server cycle SHALL sample one currently monitored eligible human using Head Hunt member weights and default weight for unlisted people. Random mode SHALL choose a capture start within the cycle and, after a curse clip is acquired, a playback time within the remaining cycle. Missing captures MUST produce no playback.

#### Scenario: Two available speakers
- **WHEN** a cycle begins with two eligible currently heard members
- **THEN** their selection probabilities follow configured weights and only the selected member can supply that cycle's clip

#### Scenario: Selected member never curses
- **WHEN** no qualifying clip is acquired before the cycle ends
- **THEN** the cycle ends silently without retaining audio for the next cycle

### Requirement: Cadence mode and safe timing fallback
Cadence mode SHALL listen for the selected member from the cycle start and play an acquired clip at its end. Random mode intervals below 60 seconds SHALL fall back to cadence with a warning. Configuration MUST bound intervals and clip duration; delayed recognition MUST NOT revive expired cycles.

#### Scenario: Short randomized interval
- **WHEN** random mode is configured with a 30-second interval
- **THEN** the runtime warns and uses 30-second cadence cycles

### Requirement: Ephemeral isolated audio playback
At most one bounded clip per server SHALL be held in memory until playback/expiry. Audio MUST NOT enter files, SQLite, logs or backups. Playback MUST stay in the capture channel using in-process PCM encoding. The visible notice MUST disclose replay and the captured-clip lifecycle.

#### Scenario: Clip completes
- **WHEN** a captured clip finishes playback or expires
- **THEN** its RAM buffer is released without creating an audio archive

### Requirement: Captured clip lifecycle
Before capture, opt-out/deletion/disable, changed assignment or excluded/departed speakers MUST cancel the selection. Once captured, a clip SHALL remain scheduled despite those changes; it MUST NOT be rerouted from its original channel. Reload and shutdown MUST clear RAM-only clips.

#### Scenario: Opt out after capture
- **WHEN** the selected member opts out after capture
- **THEN** the captured clip remains scheduled and may finish replay while future collection stops

#### Scenario: Bot moves channels
- **WHEN** the capture assignment changes before playback
- **THEN** the captured clip is never played to a different channel and is skipped if the original listener is unavailable at playback
