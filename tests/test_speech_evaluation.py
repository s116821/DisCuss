from __future__ import annotations

import asyncio
import json
from pathlib import Path

from scripts.evaluate_speech import load_case

from discuss.speech import SpeechWord


def test_synthetic_overload_conserves_work_and_separates_members(tmp_path: Path) -> None:
    class Backend:
        def transcribe(self, chunk):
            return [SpeechWord("violet", 0), SpeechWord("moon", 0.1)]

    result = asyncio.run(load_case(tmp_path, Backend(), bytes(38400), 8))
    assert result["accepted_streams"] + result["rejected_streams"] == result["offered_streams"] == 8
    assert result["max_queue_observed"] == result["queue_cap"] == 4
    assert result["processed"] == 4 and result["failures"] == 0
    assert result["detections_by_synthetic_member"] == {str(m): 1 for m in range(100, 104)}
    assert "violet" not in json.dumps(result) and "pcm" not in json.dumps(result)
