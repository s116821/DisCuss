# Proposal

## Why
The operator wants the previous plain-text speaker attribution restored. Profile-linked names added for history lookup look like hard tags and distract from the alert.

## What Changes
- Restore escaped plain-text names in detection reports, without profile links or mentions.
- Retain historical linked-report parsing and the existing conservative plain-name lookup; document its attribution limits.
- Remove private-repository references from both public projects and audit editable project metadata, retaining third-party license notices.
- Release and update the local service, enabling sampled playback at defaults as separately requested.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `contextual-detection-reporting`: plain-text speaker presentation.
- `published-quote-history`: distinguish current plain-text reports from historical linked reports.

## Impact
One renderer, its existing regression expectations, explanatory docs and canonical specifications. No new quote storage, identity database, tracking metadata or Discord production testing.
