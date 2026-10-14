"""Fetch two checksum-verified published bundles for native upgrade acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from packaging.version import Version


def fetch(platform: str, root: Path) -> list[str]:
    releases = json.loads(
        subprocess.check_output(
            [
                "gh",
                "release",
                "list",
                "--repo",
                os.environ["GITHUB_REPOSITORY"],
                "--limit",
                "100",
                "--json",
                "tagName,isPrerelease,isDraft",
            ],
            text=True,
        )
    )
    tags = sorted(
        (r["tagName"] for r in releases if not r["isDraft"] and not r["isPrerelease"]),
        key=lambda t: Version(t.removeprefix("v")),
    )[-2:]
    if len(tags) != 2:
        raise ValueError("Native upgrade acceptance requires two published application releases")
    suffix = "zip" if platform == "windows-x64" else "tar.gz"
    for index, tag in enumerate(tags):
        target = root / str(index)
        target.mkdir(parents=True)
        name = f"DisCuss-{tag}-{platform}.{suffix}"
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                os.environ["GITHUB_REPOSITORY"],
                "--pattern",
                name,
                "--pattern",
                "SHA256SUMS",
                "--dir",
                str(target),
            ],
            check=True,
        )
        entries = {
            line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in (target / "SHA256SUMS").read_text().splitlines()
        }
        if hashlib.sha256((target / name).read_bytes()).hexdigest() != entries.get(name):
            raise ValueError("Published bundle checksum mismatch")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write(f"first={tags[0]}\nsecond={tags[1]}\n")
    return tags


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("linux-x64", "windows-x64"))
    parser.add_argument("--output", type=Path, default=Path("previous"))
    args = parser.parse_args()
    print(fetch(args.platform, args.output))
