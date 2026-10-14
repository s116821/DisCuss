"""Build once from the candidate local tag and record immutable artifact receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from scripts.create_release import ROOT, artifact_version, assemble


def git(*args: str) -> str:
    return subprocess.check_output(["pwsh", "-File", str(ROOT / "scripts/git.ps1"), *args], cwd=ROOT, text=True).strip()


def build(platform: str, candidate: str = "") -> str:
    output = ROOT / "dist"
    if output.exists() and any(output.iterdir()):
        raise ValueError("Build output must be empty")
    commit = git("rev-parse", "HEAD")
    if candidate:
        # This tag exists only in the disposable build checkout. Never push it.
        git("tag", candidate, commit)
    os.environ["SOURCE_DATE_EPOCH"] = git("show", "-s", "--format=%ct", commit)
    subprocess.run(["uv", "build"], cwd=ROOT, check=True)
    subprocess.run(
        [
            "uv",
            "export",
            "--quiet",
            "--locked",
            "--extra",
            "runtime",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            "runtime-requirements.txt",
        ],
        cwd=ROOT,
        check=True,
    )
    tag = candidate or "v" + artifact_version(next(output.glob("*.whl")))
    assets = assemble(ROOT, output, tag, platform)
    receipt = {
        "source_commit": commit,
        "tag": tag,
        "platform": platform,
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets},
    }
    (output / "build-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"tag={tag}\n")
    return tag


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("linux-x64", "windows-x64"))
    parser.add_argument("--candidate", default="")
    args = parser.parse_args()
    print(build(args.platform, args.candidate))
