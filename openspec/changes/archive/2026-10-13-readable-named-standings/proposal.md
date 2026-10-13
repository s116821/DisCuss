# Why
Temporary-server testing exposed cluttered ID-based standings and per-word sections in every report. The operator wants readable totals/rates, recognizable people/channel names throughout Discord output, and word counts only when explicitly selecting a member.

# What Changes
- Clear ranked total/rate sections and local calendar labels, without automatic word breakdowns.
- Resolve account/display names in standings, scheduled reports, word queries and status; use neutral labels if Discord cannot resolve an identity.
- Keep scheduled snapshot/page receipts immutable with reserved internal member-name slots resolved at delivery. Sanitize earlier queued ID/word sections before publishing.
- Require the member selector for the dedicated words command.
- Preserve personal opt-out/in and administrator-only server controls; detection alerts start directly with the quote and have no recognition header.

# Capabilities
## Modified Capabilities
- `calendar-reporting`: readable name-based summaries without per-word sections.
- `application-runtime`: explicit member-only word queries and named diagnostics.

# Impact
Reporting renderer/outbox presentation, SDK name resolution and commands, docs and offline regression coverage. Statistics/window math, receiver, tokens and release gates are unchanged. Fold into the existing reporting PR before merging both stacks as authorized.
