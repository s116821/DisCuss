from __future__ import annotations

from pathlib import Path

from scripts.check_openspec import git_output, problems


def test_git_wrapper_forwards_path_separator() -> None:
    # Exercise the same argument shape as CI, including the standalone --.
    base = git_output("rev-list", "--max-parents=0", "HEAD").strip()
    output = git_output("diff", "--name-only", base, "HEAD", "--", "openspec/changes/archive")
    assert "openspec/changes/archive/" in output


def fixture(root: Path) -> Path:
    (root / "openspec").mkdir()
    (root / "openspec/config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    archive = root / "openspec/changes/archive/2026-10-13-fixture"
    archive.mkdir(parents=True)
    for name in ("proposal.md", "design.md", "verification.md", ".openspec.yaml"):
        (archive / name).write_text("complete", encoding="utf-8")
    (archive / "tasks.md").write_text("- [x] Task\n", encoding="utf-8")
    delta = archive / "specs/example/spec.md"
    delta.parent.mkdir(parents=True)
    block = (
        "### Requirement: Example\nThe system SHALL work.\n\n#### Scenario: Check\n- **WHEN** used\n- **THEN** works\n"
    )
    delta.write_text("## ADDED Requirements\n\n" + block, encoding="utf-8")
    spec = root / "openspec/specs/example/spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("## Requirements\n\n" + block, encoding="utf-8")
    return archive


def test_complete_and_synchronized_passes(tmp_path: Path) -> None:
    fixture(tmp_path)
    assert problems(tmp_path) == []


def test_active_change_fails(tmp_path: Path) -> None:
    fixture(tmp_path)
    (tmp_path / "openspec/changes/active").mkdir()
    assert any("Unarchived" in p for p in problems(tmp_path))


def test_incomplete_archive_fails(tmp_path: Path) -> None:
    archive = fixture(tmp_path)
    (archive / "tasks.md").write_text("- [ ] Unfinished\n", encoding="utf-8")
    assert any("unfinished" in p for p in problems(tmp_path))


def test_unsynchronized_spec_fails(tmp_path: Path) -> None:
    fixture(tmp_path)
    (tmp_path / "openspec/specs/example/spec.md").write_text("## Requirements\n", encoding="utf-8")
    assert any("unsynchronized" in p for p in problems(tmp_path))


def test_old_archives_can_be_superseded(tmp_path: Path) -> None:
    fixture(tmp_path)
    (tmp_path / "openspec/specs/example/spec.md").write_text("newer requirement", encoding="utf-8")
    assert problems(tmp_path, changed_archives=set()) == []


def test_explicit_same_pr_supersession_checks_replacement(tmp_path: Path) -> None:
    previous = fixture(tmp_path)
    replacement = previous.with_name("2026-10-13-replacement")
    replacement.mkdir()
    for name in ("proposal.md", "design.md", "tasks.md", "verification.md"):
        (replacement / name).write_text((previous / name).read_text())
    (replacement / ".openspec.yaml").write_text(f"supersedes: {previous.name}\n")
    delta = replacement / "specs/example/spec.md"
    delta.parent.mkdir(parents=True)
    content = (
        (previous / "specs/example/spec.md")
        .read_text()
        .replace("ADDED", "MODIFIED")
        .replace("SHALL work", "SHALL discover")
    )
    delta.write_text(content)
    canonical = tmp_path / "openspec/specs/example/spec.md"
    canonical.write_text(content)
    changed = {previous.name, replacement.name}
    assert problems(tmp_path, changed) == []
    (replacement / ".openspec.yaml").write_text("")
    (replacement / "supersedes.yaml").write_text(f"supersedes: {previous.name}\n")
    assert problems(tmp_path, changed) == []
    canonical.write_text("## Requirements\n")
    assert any("replacement" in error and "unsynchronized" in error for error in problems(tmp_path, changed))
    assert any("unsynchronized" in error for error in problems(tmp_path, {previous.name}))
    (previous / ".openspec.yaml").write_text(f"supersedes: {replacement.name}\n")
    canonical.write_text(content)
    assert any("cyclic" in error for error in problems(tmp_path, changed))


def test_supersession_must_reference_existing_different_archive(tmp_path: Path) -> None:
    previous = fixture(tmp_path)
    for name in ("nonexistent", previous.name):
        (previous / ".openspec.yaml").write_text(f"supersedes: {name}\n")
        assert any("invalid superseded" in error for error in problems(tmp_path))
