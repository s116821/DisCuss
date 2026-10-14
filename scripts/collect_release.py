"""Verify both platform build receipts and collect saved bytes without rebuilding."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from scripts.create_release import artifact_version


def collect(source: Path, output: Path, tag: str, commit: str) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Publication output must be empty")
    selected: list[Path] = []
    for platform, suffix in (("linux-x64", "tar.gz"), ("windows-x64", "zip")):
        directory = source / f"build-{platform}"
        receipt = json.loads((directory / "build-receipt.json").read_text(encoding="utf-8"))
        if (receipt["source_commit"], receipt["tag"], receipt["platform"]) != (commit, tag, platform):
            raise ValueError("Build receipt does not match final release source/version/platform")
        names = set(receipt["files"])
        if names != {p.name for p in directory.iterdir() if p.name != "build-receipt.json"}:
            raise ValueError("Build contains unrecorded or missing artifacts")
        for name, digest in receipt["files"].items():
            if Path(name).name != name or hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Build artifact checksum mismatch")
        wheels = list(directory.glob("*.whl"))
        sources = [p for p in directory.glob("*.tar.gz") if p.name.startswith("discuss-")]
        archive = directory / f"DisCuss-{tag}-{platform}.{suffix}"
        if len(wheels) != 1 or len(sources) != 1 or not archive.is_file():
            raise ValueError("Expected package distributions and platform archive")
        for path in wheels + sources:
            if artifact_version(path) != tag.removeprefix("v"):
                raise ValueError("Package metadata differs from final release version")
        selected.append(archive)
        if platform == "linux-x64":
            selected.extend(wheels + sources)
    output.mkdir(parents=True, exist_ok=True)
    for path in selected:
        shutil.copyfile(path, output / path.name)
    (output / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(output.iterdir())),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    collect(args.source, args.output, args.tag, args.commit)
