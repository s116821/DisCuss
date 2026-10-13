# Verification

Windows offline: all 76 tests passed (including five name/presentation tests), Ruff lint/format and ty passed, 13 actual release-analyzer cases passed, source/wheel builds succeeded, and the delta passes strict OpenSpec validation. Additional lookup-timeout and dense-legacy regressions pass after the full run.

Verified: ranked totals/rates keep the same calendar math and eligibility; local period dates and escaped names; no per-word sections or IDs in normal output; explicit required member selection exposes only that member's word counts; named server/channel/bot diagnostics; missing profiles use neutral labels with bounded retries; frozen padded member slots preserve page boundaries without storing names; UTF16 limits, mention safety and one-pass legacy replacement; unchanged per-page retry, concurrent receipt, deletion/retention tests; caller-only opt-out/in and administrator-only monitoring. Detection messages begin with the quote, with no recognition header.

The operator observed detection/reporting in the authorized temporary server. Full multi-speaker/DAVE/rekey/OS reboot qualification remains separate. No production/community server was used. Cross-platform PR CI will run before the requested stack merges. Legacy queued reports may shorten long names to preserve their existing page receipt boundaries.
