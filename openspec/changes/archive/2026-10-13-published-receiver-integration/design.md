# Design

Consume discord-voice-reception==1.0.0 from PyPI instead of tool.uv.sources. Verify the existing GitHub/PyPI artifact hashes and source equivalence, then retain uv's exact artifact hashes in the lockfile and exported native runtime requirements. Existing assembly already records a version rather than a URL for PyPI dependencies and chooses binary installation. Fixture coverage continues to exercise both immutable-source and exact-PyPI dependency paths. Main CI and actual released asset smoke remain automatic; no publication readiness gate is introduced.
