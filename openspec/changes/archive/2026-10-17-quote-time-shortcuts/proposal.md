# Proposal

## Why
Quote searches should accept a clock time without repeating today's date. Current errors do not explain timezone offsets or required leading zeros.

## What Changes
- Accept time-only `HH:MM` and `HH:MM±HH:MM`, using today's date in the configured server timezone.
- Use the configured timezone for offset-free inputs and honor explicit UTC offsets.
- Explain leading zeros, offset syntax and defaults in errors, command hints and documentation; retain existing range and clock-change safeguards.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `published-quote-history`: explicit supported query timestamp forms and defaults.

## Impact
Quote query bounds parsing, command descriptions, documentation and offline boundary/error coverage. No new storage or Discord permissions.
