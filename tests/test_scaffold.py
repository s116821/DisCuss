from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from packaging.version import Version
from scripts.create_release import artifact_version, assemble

ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
MODULE = "discuss" if PROJECT["project"]["name"] == "discuss" else "discord_voice_reception"


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["pwsh", "-File", str(ROOT / "scripts/git.ps1"), *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_dynamic_version_only() -> None:
    assert PROJECT["project"]["dynamic"] == ["version"]
    assert "version" not in PROJECT["project"]
    assert PROJECT["tool"]["hatch"]["version"]["source"] == "uv-dynamic-versioning"
    assert PROJECT["tool"]["uv-dynamic-versioning"] == {
        "vcs": "git",
        "style": "pep440",
        "fallback-version": "0.0.0",
    }


def test_runtime_metadata_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(f"{MODULE}.version")
    assert isinstance(Version(module.service_version()), Version)
    monkeypatch.setattr(module, "version", lambda name: "1.2.3")
    assert module.service_version() == "1.2.3"

    def missing(name: str) -> str:
        raise module.PackageNotFoundError(name)

    monkeypatch.setattr(module, "version", missing)
    assert module.service_version() == "0.0.0"


def test_actual_tag_build_and_release_assets(tmp_path: Path) -> None:
    repo = tmp_path / "tagged"
    repo.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", ".gitignore", ".python-version"):
        shutil.copy2(ROOT / name, repo / name)
    shutil.copytree(ROOT / "src", repo / "src", ignore=shutil.ignore_patterns("__pycache__"))
    if (ROOT / "deploy").exists():
        shutil.copytree(ROOT / "deploy", repo / "deploy")
        shutil.copytree(ROOT / "docs", repo / "docs")
        shutil.copy2(ROOT / "config.example.json", repo / "config.example.json")
        (repo / "runtime-requirements.txt").write_text("# Synthetic assembly fixture only\n")
    run_git(repo, "init")
    run_git(repo, "add", ".")
    run_git(
        repo,
        "-c",
        "user.name=s116821",
        "-c",
        "user.email=99853371+s116821@users.noreply.github.com",
        "commit",
        "-m",
        "chore(fixture): initialize",
    )
    run_git(repo, "tag", "v1.2.3")
    assert run_git(repo, "describe", "--tags", "--abbrev=0") == "v1.2.3"
    subprocess.run(["uv", "build", "--out-dir", str(repo / "dist")], cwd=repo, check=True, capture_output=True)
    wheel = next((repo / "dist").glob("*.whl"))
    assert artifact_version(wheel) == "1.2.3"
    assets = assemble(repo, repo / "dist", "v1.2.3")
    assert (repo / "dist/SHA256SUMS").is_file()
    assert all("1.2.3" in p.name or p.name == "SHA256SUMS" for p in assets)
    if MODULE == "discuss":
        import zipfile

        with zipfile.ZipFile(repo / "dist/DisCuss-v1.2.3-windows-x64.zip") as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            assert manifest["receiver_requires_build"] is False
            assert manifest["receiver"] == "1.0.0"
            assert "qualification-status.md" in bundle.namelist()
    with pytest.raises(ValueError, match="metadata does not match"):
        # Fresh build output: exclude the already created deployment tarball.
        clean = tmp_path / "mismatch"
        clean.mkdir()
        for p in (repo / "dist").iterdir():
            if p.name.startswith(PROJECT["project"]["name"].replace("-", "_")):
                shutil.copy2(p, clean / p.name)
        assemble(repo, clean, "v9.9.9")


def test_gitignore_covers_local_secrets() -> None:
    for pattern in ("config.json", ".env", ".venv/lib", "data/example.db", "models/weights", "secret.token"):
        result = subprocess.run(
            ["pwsh", "-File", str(ROOT / "scripts/git.ps1"), "check-ignore", "-q", pattern],
            cwd=ROOT,
        )
        assert result.returncode == 0, pattern


def test_reference_analyzer_config_and_release_gate() -> None:
    config = json.loads((ROOT / ".releaserc.json").read_text(encoding="utf-8"))
    plugin, options = config["plugins"][0]
    assert plugin == "@semantic-release/commit-analyzer"
    assert options["preset"] == "conventionalcommits"
    assert {"type": "docs", "release": False} in options["releaseRules"]
    assert {"breaking": True, "release": "major"} in options["releaseRules"]
    assert not (ROOT / f"src/{MODULE}/release_policy.py").exists()
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    for gate in ("ruff check", "ruff format --check", "ty check", "pytest", "test:release", "spec:validate"):
        assert gate in ci
    assert "needs: quality" in ci
    assert "uses: ./.github/workflows/release.yml" in ci
    assert "workflow_call:" in release and "push:" not in release
    assert "RELEASE_READY" not in ci
    assert "check_release_ready" not in release
    pr = (ROOT / ".github/workflows/pr-title.yml").read_text(encoding="utf-8")
    assert "requireScope: true" in pr
    assert "fetch-depth: 0" in ci and "fetch-depth: 0" in release


def test_ruff_rejects_invalid_source(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def bad(\n", encoding="utf-8")
    result = subprocess.run(["uv", "run", "--locked", "ruff", "check", str(bad)], cwd=ROOT, capture_output=True)
    assert result.returncode != 0


def test_no_static_version_constant() -> None:
    source = (ROOT / f"src/{MODULE}/version.py").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^__version__\s*=", source)
