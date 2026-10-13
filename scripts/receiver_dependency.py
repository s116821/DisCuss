"""Describe the reproducibly pinned receiver for release manifests."""

from __future__ import annotations

import re
import tomllib
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
