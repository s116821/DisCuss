"""Standalone stdlib recovery utility; does not import/migrate application state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(root: Path, *, allow_development: bool = False) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest["tag"] != "v" + manifest["version"]:
        raise ValueError("Manifest version/tag mismatch")
    if not manifest["qualified_dependency"] and not allow_development:
        raise ValueError("Development bundle cannot be installed without explicit offline development opt-in")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or sha256(root / name) != expected:
            raise ValueError("Bundle file integrity failure")
    return manifest


def copy_database(source: Path, target: Path, *, restore: bool = False) -> None:
    if target.exists() and not restore:
        raise FileExistsError("Recovery destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # SQLite's backup API includes committed WAL contents and safely replaces pages
    # in an existing destination; never raw-copy over a live/stale WAL database.
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as reader:
        if reader.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Source database integrity failure")
        with sqlite3.connect(target) as writer:
            reader.backup(writer)
            if writer.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Recovery database integrity failure")
    if os.name != "nt":
        target.chmod(0o600)


def backup(config: Path, state: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    if config.exists():
        shutil.copy2(config, destination / "config.json")
    database = state / "statistics.sqlite3"
    if database.exists():
        copy_database(database, destination / database.name)


def restore(config: Path, state: Path, source: Path) -> None:
    database = source / "statistics.sqlite3"
    if database.exists():
        copy_database(database, state / database.name, restore=True)
    if (source / "config.json").exists():
        shutil.copy2(source / "config.json", config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["verify", "backup", "restore"])
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--allow-development", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    if args.operation == "verify":
        verify_bundle(args.bundle, allow_development=args.allow_development)
    elif args.operation == "backup":
        backup(args.config, args.state, args.snapshot)
    else:
        restore(args.config, args.state, args.snapshot)


if __name__ == "__main__":
    main()
