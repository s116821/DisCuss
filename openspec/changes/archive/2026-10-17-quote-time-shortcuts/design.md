# Design

## Decisions
Resolve omitted dates once from the supplied current instant in the configured server timezone, including when a clock time carries its own UTC offset. This makes both endpoints use the same local current date instead of guessing an overnight range or deriving a date from the other endpoint. Offset-free inputs use server timezone; explicit offsets identify an exact instant. User timezone is not inferred from locale or device settings.

Validate documented zero-padded forms before datetime parsing, including offset minute ranges so invalid offsets cannot silently normalize. Keep date-only and full ISO timestamp inputs, optional seconds/fractions and Z compatibility. Preserve default seven-day range, exclusive end, future/size limits and rejection of ambiguous/nonexistent offset-free clock-change times.

## Verification
Cover time-only inputs with and without offsets, server-local dates across UTC midnight, explicit-date compatibility, malformed padding/offsets, DST folds/gaps and range guards. Exercise the offline quote-command error reply and history scan bounds. Synchronize and archive the new requirement in the existing PR before release/local restart.
