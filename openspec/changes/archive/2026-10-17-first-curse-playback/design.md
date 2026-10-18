# Design

## Context

The controller currently chooses one weighted Target per server cycle. Coordinator ticks supply all eligible humans in current listener assignments; recognition offers include server/channel/member but no listener identity. Only a bounded acquired clip is retained. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** reuse current capture slicing, random replay timing, original-channel routing and captured-clip policy; keep selection and audio state bounded per server.

**Non-Goals:** hearing additional channels, retaining continuous conversations, synchronizing speech timestamps across recognition jobs, changing shipped defaults, or modifying the receiver package.

## Decisions

- Extend the mode enum with `first_curse`. Keep weighted selection for existing modes; store an eligible Target snapshot for a first-curse cycle, updated on coordinator ticks until capture. Resolve the winning Target from member plus channel when the first qualifying clip arrives. This retains listener routing without expanding speech chunks or retaining audio for every candidate.
- First means first qualifying detection processed/acquired, consistent with the existing recognition queue. Reordering by speech time would need buffering and a latency/watermark policy, delaying playback and exceeding this feature's scope.
- A candidate's opt-out removes only that candidate before acquisition; server disable/reload clears an uncaptured cycle. Eligibility updates include newcomers and current assignments. The existing allowed callback remains an immediate guard for policy changes between ticks.
- Use a shared cadence-timing property for short intervals. Existing short random configs still normalize to cadence; short first_curse configs retain all-speaker eligibility and use boundary playback. This avoids silently reverting to selecting one person.
- Once acquired, assign the winner and use existing clip slicing, playback scheduling and lifecycle. Later clips cannot overwrite it. Preserve one clip per server and force-clear on reload/shutdown.

## Risks / Trade-offs

- Recognition order can differ from utterance order → explicitly document acquisition ordering and test delayed recognition.
- Presence changes between scheduler ticks → use the latest monitored snapshot plus immediate policy checks; never accept arbitrary channel/member offers.
- Multiple listeners → test winning-listener/channel routing and rejecting stale assignments.
- Upgrade can replace operator policy accidentally → structurally verify protected config preservation, changing only enabled/mode while retaining the existing 600-second interval and both report destinations.

## Migration Plan

Existing configurations continue using their selected modes without migration. Regenerate JSON schema, update docs and release through the normal gated pipeline. Install the verified native release with the standard installer, activate first_curse in the protected local config and verify fresh speech-ready boot-service health. Roll back local configuration on activation failure; preserve prior native release rollback support. Do not inject production audio or test messages.
