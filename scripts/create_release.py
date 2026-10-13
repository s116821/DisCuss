"""Verify tag-derived metadata and assemble lean release assets."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def artifact_version(path: Path) -> str:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise ValueError("Wheel must contain exactly one metadata record")
            text = archive.read(names[0]).decode("utf-8")
    else:
        with tarfile.open(path) as archive:
            members = [m for m in archive.getmembers() if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")]
            if len(members) != 1:
                raise ValueError("Source archive must contain exactly one root metadata record")
            stream = archive.extractfile(members[0])
            if stream is None:
                raise ValueError("Missing source metadata")
            text = stream.read().decode("utf-8")
    value = Parser().parsestr(text).get("Version")
    if value is None:
        raise ValueError("Missing package version")
    return value


def assemble(root: Path, output: Path, tag: str) -> list[Path]:
    if not tag.startswith("v") or str(Version(tag[1:])) != tag[1:]:
        raise ValueError("Release tag must be v followed by the canonical package version")
    wheels = list(output.glob("*.whl"))
    sources = list(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected one wheel and one sdist in a clean output directory")
    for path in wheels + sources:
        if artifact_version(path) != tag[1:]:
            raise ValueError(f"Artifact metadata does not match tag: {path.name}")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"]
    assets = wheels + sources
    if project == "discuss":
        for platform, suffix in (("windows-x64", "zip"), ("linux-x64", "gztar")):
            with tempfile.TemporaryDirectory() as directory:
                staging = Path(directory)
                shutil.copy2(wheels[0], staging / wheels[0].name)
                for name in ("LICENSE", ".python-version", "config.example.json", "runtime-requirements.txt"):
                    if (root / name).exists():
                        shutil.copy2(root / name, staging / name)
                for name in ("INSTALL.md", "install.sh", "install.ps1"):
                    if (root / "deploy" / name).exists():
                        shutil.copy2(root / "deploy" / name, staging / name)
                archive = shutil.make_archive(str(output / f"DisCuss-{tag}-{platform}"), suffix, staging)
                assets.append(Path(archive))
    checksums = output / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(assets)), encoding="utf-8"
    )
    return assets + [checksums]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    for path in assemble(ROOT, args.output.resolve(), args.tag):
        print(path.name)


if __name__ == "__main__":
    main()
