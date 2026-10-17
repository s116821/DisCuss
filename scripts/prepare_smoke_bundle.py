"""Build disposable tagged archive fixtures, without modifying the real checkout."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.create_release import assemble

ROOT = Path(__file__).resolve().parents[1]


def prepare(output: Path, tag: str = "v1.2.3") -> None:
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        for name in ("pyproject.toml", "README.md", "LICENSE", ".gitignore", "config.example.json"):
            shutil.copy2(ROOT / name, repo / name)
        for name in ("src", "deploy", "docs"):
            shutil.copytree(ROOT / name, repo / name, ignore=shutil.ignore_patterns("__pycache__"))
        for args in (
            ["init"],
            ["add", "."],
            [
                "-c",
                "user.name=s116821",
                "-c",
                "user.email=99853371+s116821@users.noreply.github.com",
                "commit",
                "-m",
                "chore(fixture): tagged installer smoke",
            ],
            ["tag", tag],
        ):
            subprocess.run(
                ["pwsh", "-File", str(ROOT / "scripts/git.ps1"), *args], cwd=repo, check=True, capture_output=True
            )
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
                str(repo / "runtime-requirements.txt"),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(["uv", "build", "--out-dir", str(output)], cwd=repo, check=True)
        assemble(repo, output, tag)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tag", default="v1.2.3")
    args = parser.parse_args()
    prepare(args.output.resolve(), args.tag)
