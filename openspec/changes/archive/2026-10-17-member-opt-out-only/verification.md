# Verification

- The existing primary-command test confirms delete_self is absent, opt-out/in affects only the caller, and the same stored counts survive both operations. Administrator controls remain protected. Startup synchronizes the primary command group, removing the obsolete registration.
- Full offline pytest: 108 passed. Ruff checks/format and ty passed. Strict change and canonical validation passed; synchronized the full primary-controls requirement including its existing authorization scenario.
- Public-reference cleanup exposed a checker scope bug for edits to historical prose. Both repositories now scope delta consistency to modified spec/supersession files while still checking every archive's completion. A regression fixture confirms prose-only edits pass, changed inconsistent deltas fail, and unfinished tasks fail even on prose-only edits.
- Operator CLI data maintenance and normal retention remain available; no production Discord messages or audio were injected for testing.
