"""Verify tag-derived metadata and assemble lean release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from urllib.parse import urlsplit

from packaging.requirements import Requirement
from packaging.version import Version


def receiver_dependency(root: Path) -> tuple[str, bool]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    items = project["project"]["optional-dependencies"]["runtime"]
    matches = [Requirement(value) for value in items if Requirement(value).name == "discord-voice-reception"]
    if len(matches) != 1:
        raise ValueError("Release requires exactly one receiver dependency")
    source = project.get("tool", {}).get("uv", {}).get("sources", {}).get("discord-voice-reception")
    url = source.get("url") if source else matches[0].url
    if source and not url:
        raise ValueError("Receiver source must be an immutable HTTPS archive")
    if url:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"/[^/]+/[^/]+/archive/[a-f0-9]{40}\.tar\.gz", parsed.path)
        ):
            raise ValueError("Receiver source must be an immutable HTTPS commit archive")
        return url, True
    specs = list(matches[0].specifier)
    if len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
        raise ValueError("Receiver requires an exact package version")
    return str(Version(specs[0].version)), False


ROOT = Path(__file__).resolve().parents[1]


def artifact_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("Wheel must contain exactly one metadata record")
        text = archive.read(names[0]).decode("utf-8")
    value = Parser().parsestr(text).get("Version")
    if value is None:
        raise ValueError("Missing package version")
    return value


def assemble(root: Path, output: Path, tag: str, platform: str | None = None) -> list[Path]:
    if not tag.startswith("v") or str(Version(tag[1:])) != tag[1:]:
        raise ValueError("Release tag must be v followed by the canonical package version")
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected one internal application wheel")
    for path in wheels:
        if artifact_version(path) != tag[1:]:
            raise ValueError(f"Artifact metadata does not match tag: {path.name}")
    assets = wheels
    receiver, requires_build = receiver_dependency(root)
    for target, suffix in (("windows-x64", "zip"), ("linux-x64", "gztar")):
        if platform is not None and platform != target:
            continue
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            shutil.copy2(wheels[0], staging / wheels[0].name)
            for name in ("LICENSE", "config.example.json", "runtime-requirements.txt"):
                shutil.copy2(root / name, staging / name)
            installer = "install.ps1" if target == "windows-x64" else "install.sh"
            for name in ("INSTALL.md", installer, "manage_state.py"):
                shutil.copy2(root / "scripts/deploy" / name, staging / name)
            for name in (
                "discord-setup.md",
                "configuration.md",
                "statistics.md",
                "privacy.md",
                "runtime.md",
                "logging.md",
                "detection-reporting.md",
                "playback.md",
                "quote-history.md",
                "qualification-status.md",
            ):
                shutil.copy2(root / "docs" / name, staging / name)
            manifest = {
                "tag": tag,
                "version": tag[1:],
                "platform": target,
                "python": "3.12.15",
                "uv": "0.13.0",
                "receiver": receiver,
                "receiver_requires_build": requires_build,
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in staging.iterdir()},
            }
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            (staging / "BUNDLE_SHA256SUMS").write_text(
                "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(staging.iterdir())),
                encoding="utf-8",
            )
            archive = shutil.make_archive(str(output / f"DisCuss-{tag}-{target}"), suffix, staging)
            assets.append(Path(archive))
    checksums = output / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(assets)), encoding="utf-8"
    )
    return assets + [checksums]


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
        archive = directory / f"DisCuss-{tag}-{platform}.{suffix}"
        if len(wheels) != 1 or not archive.is_file():
            raise ValueError("Expected internal wheel and native platform archive")
        for path in wheels:
            if artifact_version(path) != tag.removeprefix("v"):
                raise ValueError("Package metadata differs from final release version")
        selected.append(archive)
    output.mkdir(parents=True, exist_ok=True)
    for path in selected:
        shutil.copyfile(path, output / path.name)
    (output / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(output.iterdir())),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    assembly = commands.add_parser("assemble")
    assembly.add_argument("--tag", default="")
    assembly.add_argument("--platform", required=True, choices=("linux-x64", "windows-x64"))
    assembly.add_argument("--commit", required=True)
    publication = commands.add_parser("collect")
    publication.add_argument("source", type=Path)
    publication.add_argument("--tag", required=True)
    publication.add_argument("--commit", required=True)
    args = parser.parse_args()
    output = ROOT / "dist"
    if args.command == "collect":
        collect(args.source, output, args.tag, args.commit)
        return
    tag = args.tag or "v" + artifact_version(next(output.glob("*.whl")))
    assets = assemble(ROOT, output, tag, args.platform)
    receipt = {
        "source_commit": args.commit,
        "tag": tag,
        "platform": args.platform,
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets},
    }
    (output / "build-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"tag={tag}\n")


if __name__ == "__main__":
    main()
