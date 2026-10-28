# sampled-voice-playback Specification

## Purpose

Replay occasional attributed curse clips for entertainment while keeping audio bounded, ephemeral and subject to personal participation controls.

## Requirements

### Requirement: Weighted randomized replay cycle
Playback SHALL be disabled by default and use a 900-second default interval. Random and cadence modes SHALL sample one currently monitored eligible human per server cycle using Head Hunt member weights and default weight for unlisted people. Random mode SHALL choose a capture start within the cycle and, after a curse clip is acquired, a playback time within the remaining cycle. Missing captures MUST produce no playback.

#### Scenario: Two available speakers
- **WHEN** a random or cadence cycle begins with two eligible currently heard members
- **THEN** their selection probabilities follow configured weights and only the selected member can supply that cycle's clip

#### Scenario: Selected member never curses
- **WHEN** no qualifying clip is acquired before the cycle ends
- **THEN** the cycle ends silently without retaining audio for the next cycle

### Requirement: Cadence mode and safe timing fallback
Cadence mode SHALL listen for the selected member from the cycle start and play an acquired clip at its end, with a minimum five-second interval. Random and first_curse modes SHALL require intervals of at least 120 seconds; shorter values MUST fail validation without silently changing timing or eligibility. Configuration MUST bound intervals and clip duration; delayed recognition MUST NOT revive expired cycles.

#### Scenario: Short randomized interval
- **WHEN** random mode is configured with an interval below 120 seconds
- **THEN** configuration validation rejects it with an actionable minimum-interval error

#### Scenario: Short first-curse interval
- **WHEN** first_curse mode is configured with an interval below 120 seconds
- **THEN** configuration validation rejects it without switching to cadence timing or selecting a speaker

#### Scenario: Minimum randomized interval
- **WHEN** random or first_curse is configured with a 120-second interval
- **THEN** validation accepts the configuration and randomized listening/replay timing is retained

### Requirement: Ephemeral isolated audio playback
At most one bounded clip per server SHALL be held in memory until playback/expiry. Audio MUST NOT enter files, SQLite, logs or backups. Playback MUST stay in the capture channel using in-process PCM encoding. The visible notice MUST disclose replay and the captured-clip lifecycle.

#### Scenario: Clip completes
- **WHEN** a captured clip finishes playback or expires
- **THEN** its RAM buffer is released without creating an audio archive

### Requirement: Captured clip lifecycle
Before capture, opt-out/deletion/disable, changed assignment or excluded/departed speakers MUST cancel the selection or remove their first-curse eligibility. Once captured, a clip SHALL remain scheduled despite those changes; it MUST NOT be rerouted from its original channel. Reload and shutdown MUST clear RAM-only clips.

#### Scenario: Opt out after capture
- **WHEN** the selected member opts out after capture
- **THEN** the captured clip remains scheduled and may finish replay while future collection stops

#### Scenario: Bot moves channels
- **WHEN** the capture assignment changes before playback
- **THEN** the captured clip is never played to a different channel and is skipped if the original listener is unavailable at playback

#### Scenario: One candidate opts out before capture
- **WHEN** a first-curse candidate opts out before capture while another eligible human remains monitored
- **THEN** future clips from that candidate are rejected and the remaining human can still supply the cycle's clip

### Requirement: First-curse replay cycle
The optional first_curse mode SHALL accept the first qualifying detection processed from any currently monitored eligible human after a randomized listening start. It MUST NOT preselect a person or apply speaker weights. After acquisition it SHALL choose replay time within the remaining cycle, retaining the winning listener/channel. Later detections MUST NOT replace the clip. Missing captures SHALL end silently.

#### Scenario: Another monitored speaker curses first
- **WHEN** multiple eligible speakers are heard after listening starts and one supplies the first qualifying processed detection
- **THEN** that speaker supplies the sole clip regardless of member priority weights, and replay scheduling starts only after acquisition

#### Scenario: Current monitored assignments change
- **WHEN** a new eligible human is heard or an existing human leaves or changes channel before capture
- **THEN** eligibility follows the latest monitored assignments and unmonitored speakers/channels cannot supply a clip

#### Scenario: Multiple listener identities
- **WHEN** the first qualifying detection comes from a secondary listener's monitored channel
- **THEN** replay uses that listener and channel, even if other listeners heard later detections

#### Scenario: Expired detection
- **WHEN** recognition finishes after the current cycle expires or only speech before listening start is available
- **THEN** that speech cannot supply the cycle's clip
