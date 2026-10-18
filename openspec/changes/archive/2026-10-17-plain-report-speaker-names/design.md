# Design

## Decisions
Render the existing resolved speaker name through safe_text directly, keeping quote/em-dash/time and mention suppression unchanged. Do not attach hidden links or introduce content retention to compensate for the formatting change.

Quote lookup already supports plain labels using retained minimal event metadata and a unique member in the displayed minute. Preserve that conservative path and parsing of previously linked reports; ambiguous plain labels are skipped, and renames or retired minimal metadata may make them unavailable. Document that tradeoff rather than guess attribution.

## Verification and rollout
Update the existing exact-format/grouping/digest assertions, retaining escaping, mention suppression, bounds and historical parsing coverage. Run required quality/spec checks, synchronize and archive in the same PR under DEG-47. Merge successful builds, verify the published bundle, then upgrade the protected local service with playback.enabled=true at 900-second random defaults. Existing report destinations and data remain unchanged. The refreshed metadata-only audit confirms Speak in all accessible voice channels; no real-server audio test will be performed.

## Public documentation cleanup

Remove private project identifiers, repository URLs and associated private commit references from current public documentation and archived planning prose in both repositories. Keep required third-party NOTICE/license material. Audit editable public GitHub metadata for equivalent references; Git history is not rewritten. Receiver changes are documentation-only and need no specification change.
