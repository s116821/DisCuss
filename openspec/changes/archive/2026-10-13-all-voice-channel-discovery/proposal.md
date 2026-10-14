# Discover every voice channel for Head Hunt

## Why
The operator wants the boot-started bot to roam every voice channel in the deployment server without maintaining channel IDs when channels are created or removed.

## What Changes
Add head_hunt.all_channels and excluded_channel_ids. Preserve existing explicit voice_channels policies by default; automatic mode uses current SDK discovery each evaluation and applies the existing permission/fullness/member/affinity filters. Document that one identity monitors one selected channel at a time.

## Capabilities
### Modified Capabilities
- `monitoring-policy`: dynamically discover all eligible server voice channels.

## Impact
Typed config/schema/example, pure selection policy, offline tests and setup docs. No production-server tests or persistent extra discovery state.
