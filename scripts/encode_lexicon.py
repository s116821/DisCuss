"""Reencode a controlled local word file without retaining or printing plaintext."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import zlib
from pathlib import Path

from discuss.lexicon import normalize_entry


def encode(input_path: Path, output_path: Path) -> None:
    words = sorted(
        {normalize_entry(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()}
    )
    raw = json.dumps(words, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "format": 1,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "encoded": base64.b85encode(zlib.compress(raw, 9)).decode("ascii"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Private local plaintext, outside the repository")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    encode(args.input, args.output)


if __name__ == "__main__":
    main()
