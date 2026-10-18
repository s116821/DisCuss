# Verification

- Focused quote-history tests: 14 passed. Covers configured-zone time-only interpretation, explicit positive/negative offsets, server-local today across UTC midnight, another configured timezone, seconds/fractions/Z and existing full dated timestamps.
- Invalid leading zeros and offset values receive explicit guidance. DST folds/gaps still require an offset, explicit fold offsets identify distinct instants, and future/reversed/empty ranges remain rejected. The offline command callback returns the explanatory hint without reading history.
- Full offline app suite: 119 passed; Ruff checks/format and ty passed. Strict change/canonical validation passed; the new requirement was synchronized without altering existing lookup or attribution requirements.
- No production message/audio testing. Hosted checks, verified publication and local upgrade/restart with enabled playback remain tracked under DEG-47.
