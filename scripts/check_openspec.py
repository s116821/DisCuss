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
    superseded: set[tuple[str, Path, str]] = set()
    replacement_edges: dict[str, str] = {}
    for archive in archives:
        metadata = archive / ".openspec.yaml"
        text = metadata.read_text(encoding="utf-8") if metadata.exists() else ""
        supplemental = archive / "supersedes.yaml"
        if supplemental.exists():
            text += "\n" + supplemental.read_text(encoding="utf-8")
        replaces = re.search(r"(?m)^supersedes: ([a-z0-9-]+)\s*$", text)
        if not replaces:
            continue
        previous = replaces.group(1)
        if previous == archive.name or previous not in {a.name for a in archives}:
            errors.append(f"{archive.name}: invalid superseded archive: {previous}")
            continue
        replacement_edges[archive.name] = previous
        # Only a delta in the checked scope may replace an earlier checked delta.
        if changed_archives is not None and archive.name not in changed_archives:
            continue
        for delta in (archive / "specs").rglob("spec.md"):
            capability = delta.relative_to(archive / "specs")
            for section in re.split(r"(?m)^## ", delta.read_text(encoding="utf-8"))[1:]:
                if section.splitlines()[0].strip() in {"MODIFIED Requirements", "REMOVED Requirements"}:
                    superseded.update((previous, capability, name) for name in blocks(section))
    for start in replacement_edges:
        seen: set[str] = set()
        current_archive = start
        while current_archive in replacement_edges:
            if current_archive in seen:
                errors.append(f"{start}: cyclic archive supersession")
                break
            seen.add(current_archive)
            current_archive = replacement_edges[current_archive]
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
                    if (archive.name, capability, name) in superseded:
                        continue
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
        # Historical prose edits do not revive requirements replaced years ago.
        # Completion is still checked for every archive; recheck consistency
        # when a delta or its supersession metadata actually changes.
        changed = {
            parts[3]
            for path in paths
            if len(parts := path.split("/")) > 4
            and (parts[4] == "specs" or parts[4] in {".openspec.yaml", "supersedes.yaml"})
        }
    errors = problems(ROOT, changed)
    for error in errors:
        print(error)
    if not errors:
        print("OpenSpec merge readiness passed")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
