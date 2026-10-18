# Verification

- Installed locked development and runtime dependencies and pinned Node tooling without dependency changes.
- Full offline suite: 132 passed. Focused playback suite: 25 passed.
- Ruff check, Ruff format check and ty pass. Strict validation passes for the change and all 14 canonical capabilities.
- Config/schema accepts first_curse without changing shipped defaults; short cycles retain all-speaker eligibility while using cadence timing.
- Controller coverage verifies random listening start, first-acquired ordering, no weighted preselection, post-acquisition scheduling, bounded clips, original secondary-listener routing, no replacement and no duplicate playback.
- Eligibility coverage rejects unmonitored/old channels, departed or opted-out candidates, disabled monitoring/playback and expired/pre-window speech; new arrivals and remaining eligible candidates can supply a clip.
- Pipeline/Coordinator integration covers ephemeral memory playback after opt-out/departure, no audio in SQLite, multiple monitored listeners, handoff without resetting another listener's cycle, and shutdown clearing the clip.
- Canonical sync verified against every delta block; existing title, Purpose and the untouched ephemeral-audio requirement are preserved.
- All tracked tasks complete; archived consistency gate passes with the explicit playback-spec supersession.
- Operator documentation explains all modes, recognition-order semantics, audible-channel scope, short-interval behavior and unchanged clip lifecycle.

Native build/install lifecycle verification runs in the existing gated platform jobs. Release verification and local operator activation are post-merge workflow follow-ups tracked outside this archive. No production test audio or test messages were injected.
