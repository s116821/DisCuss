from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from deploy.manage_state import backup, copy_database, restore, verify_bundle
from scripts.receiver_dependency import receiver_dependency


def test_backup_includes_wal_without_migrating_and_restore_replaces_pages(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"sentinel":"protected-original"}')
    state = tmp_path / "state"
    state.mkdir()
    path = state / "statistics.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA user_version=1")
    db.execute("CREATE TABLE original(value TEXT)")
    db.execute("INSERT INTO original VALUES ('committed-wal')")
    db.commit()
    snapshot = tmp_path / "backup"
    backup(config, state, snapshot)
    assert (snapshot / "config.json").read_text() == config.read_text()
    with sqlite3.connect(snapshot / path.name) as saved:
        assert saved.execute("SELECT value FROM original").fetchone()[0] == "committed-wal"
        assert saved.execute("PRAGMA user_version").fetchone()[0] == 1
    db.execute("INSERT INTO original VALUES ('after-upgrade')")
    db.commit()
    db.close()
    config.write_text("changed")
    restore(config, state, snapshot)
    with sqlite3.connect(path) as restored:
        assert restored.execute("SELECT value FROM original").fetchall() == [("committed-wal",)]
    assert "protected-original" in config.read_text()
    with pytest.raises(FileExistsError):
        copy_database(path, snapshot / path.name)


def test_development_bundle_installs_normally_and_corruption_is_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "payload.whl"
    payload.write_bytes(b"fixture")
    manifest = {
        "tag": "v1.2.3",
        "version": "1.2.3",
        "receiver_requires_build": True,
        "files": {payload.name: hashlib.sha256(payload.read_bytes()).hexdigest()},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert verify_bundle(tmp_path)["version"] == "1.2.3"
    payload.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        verify_bundle(tmp_path)


def test_release_records_exact_sources_and_rejects_mutable_dependencies(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source, build = receiver_dependency(root)
    assert "b68549dd0b45435d7e7e12de5fd6e0982d107e86" in source and build
    for version in ("1.0.0rc1", "1.0.0.dev1", "1.2.3"):
        (tmp_path / "pyproject.toml").write_text(
            '[project.optional-dependencies]\nruntime=["discord-voice-reception==' + version + '"]'
        )
        assert receiver_dependency(tmp_path) == (version, False)
    (tmp_path / "pyproject.toml").write_text(
        '[project.optional-dependencies]\nruntime=["discord-voice-reception>=1.2.3"]'
    )
    with pytest.raises(ValueError, match="exact"):
        receiver_dependency(tmp_path)
    for revision in ("main", "v1.2.3", "b68549dd"):
        (tmp_path / "pyproject.toml").write_text(
            '[project.optional-dependencies]\nruntime=["discord-voice-reception==0.0.0"]\n'
            '[tool.uv.sources]\ndiscord-voice-reception={url="https://github.com/s116821/'
            f'DiscordVoiceReception/archive/{revision}.tar.gz"}}'
        )
        with pytest.raises(ValueError, match="immutable"):
            receiver_dependency(tmp_path)
