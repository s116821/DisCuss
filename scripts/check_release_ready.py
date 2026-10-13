"""Reject a development/non-stable receiver before semantic-release tags anything."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


def receiver_pin(root: Path) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if "discord-voice-reception" in project.get("tool", {}).get("uv", {}).get("sources", {}):
        raise ValueError("Release blocked: receiver is a development source; qualify and pin stable PyPI version")
    items = project["project"]["optional-dependencies"]["runtime"]
    matches = [Requirement(value) for value in items if Requirement(value).name == "discord-voice-reception"]
    if len(matches) != 1:
        raise ValueError("Release requires exactly one receiver dependency")
    dep = matches[0]
    specs = list(dep.specifier)
    if dep.url or len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
        raise ValueError("Release requires an exact stable receiver PyPI pin")
    version = Version(specs[0].version)
    if version.is_prerelease or version.is_devrelease or version.local or version == Version("0.0.0"):
        raise ValueError("Receiver pin is not a qualified stable version")
    return str(version)


if __name__ == "__main__":
    print(receiver_pin(Path(__file__).resolve().parents[1]))
