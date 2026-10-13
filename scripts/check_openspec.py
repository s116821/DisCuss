"""Enforce merge-ready archives and newly changed delta/canonical consistency."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git_output(*args: str) -> str:
    return subprocess.run(
        ["pwsh", "-File", str(ROOT / "scripts/git.ps1"), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def blocks(text: str) -> dict[str, str]:
    result = {}
    for match in re.finditer(r"(?m)^### Requirement: (.+)\n", text):
        end = re.search(r"(?m)^#{1,3} ", text[match.end() :])
        block_end = match.end() + end.start() if end else len(text)
        result[match.group(1).strip()] = text[match.start() : block_end].strip()
    return result


def problems(root: Path, changed_archives: set[str] | None = None) -> list[str]:
    errors = []
    changes = root / "openspec/changes"
    if not (root / "openspec/config.yaml").is_file():
        errors.append("Missing OpenSpec installation")
    active = [p.name for p in changes.iterdir() if p.is_dir() and p.name != "archive"] if changes.exists() else []
    if active:
        errors.append(f"Unarchived changes: {', '.join(active)}")
    archive_root = changes / "archive"
    archives = sorted(p for p in archive_root.iterdir() if p.is_dir()) if archive_root.exists() else []
    if not archives:
        errors.append("No completed change archive exists")
    for archive in archives:
        for name in ("proposal.md", "design.md", "tasks.md", "verification.md", ".openspec.yaml"):
            if not (archive / name).is_file():
                errors.append(f"{archive.name}: missing {name}")
        tasks = (archive / "tasks.md").read_text(encoding="utf-8") if (archive / "tasks.md").exists() else ""
        markers = re.findall(r"(?m)^\s*-\s*\[([^]\n]*)\]", tasks)
        if not markers or any(marker.strip().lower() != "x" for marker in markers):
            errors.append(f"{archive.name}: missing or unfinished tasks")
        if changed_archives is not None and archive.name not in changed_archives:
            continue
        deltas = list((archive / "specs").rglob("spec.md"))
        if not deltas:
            errors.append(f"{archive.name}: missing delta specs")
        for delta in deltas:
            capability = delta.relative_to(archive / "specs")
            canonical = root / "openspec/specs" / capability
            current = blocks(canonical.read_text(encoding="utf-8")) if canonical.exists() else {}
            text = delta.read_text(encoding="utf-8")
            for section in re.split(r"(?m)^## ", text)[1:]:
                operation = section.splitlines()[0].strip()
                if operation not in {"ADDED Requirements", "MODIFIED Requirements", "REMOVED Requirements"}:
                    continue
                for name, content in blocks(section).items():
                    if operation == "REMOVED Requirements":
                        if name in current:
                            errors.append(f"{archive.name}/{capability}: removed requirement still exists: {name}")
                    elif current.get(name) != content:
                        errors.append(f"{archive.name}/{capability}: unsynchronized requirement: {name}")
    return errors


def main() -> int:
    base = os.environ.get("OPENSPEC_BASE_SHA", "")
    changed = None
    if base and set(base) != {"0"}:
        paths = git_output("diff", "--name-only", base, "HEAD", "--", "openspec/changes/archive").splitlines()
        changed = {p.split("/")[3] for p in paths if len(p.split("/")) > 3}
    errors = problems(ROOT, changed)
    for error in errors:
        print(error)
    if not errors:
        print("OpenSpec merge readiness passed")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
