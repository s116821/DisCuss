"""Explicit pinned model setup and local-only startup verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import ConfigError, Transcription


def model_path(state_dir: Path, settings: Transcription) -> Path:
    return state_dir / "models" / (settings.model_id.replace("/", "--") + "-" + settings.revision)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_model(state_dir: Path, settings: Transcription) -> Path:
    path = model_path(state_dir, settings)
    manifest = path / "model.manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data["model_id"] != settings.model_id or data["revision"] != settings.revision:
            raise ValueError("Wrong model revision")
        required = {"model.bin", "config.json", "tokenizer.json"}
        if not required <= data["files"].keys():
            raise ValueError("Incomplete model snapshot")
        if not {"vocabulary.txt", "vocabulary.json"} & data["files"].keys():
            raise ValueError("Missing model vocabulary")
        for name, expected in data["files"].items():
            if name not in {
                "model.bin",
                "config.json",
                "tokenizer.json",
                "vocabulary.json",
                "vocabulary.txt",
                "preprocessor_config.json",
            }:
                raise ValueError("Unexpected model file")
            if digest(path / name) != expected:
                raise ValueError("Model integrity mismatch")
    except (OSError, ValueError, KeyError, TypeError):
        raise ConfigError("Speech model is missing or invalid; run discuss model-setup before starting") from None
    return path


def prepare_model(state_dir: Path, settings: Transcription) -> Path:
    from huggingface_hub import snapshot_download

    path = model_path(state_dir, settings)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    allowed = [
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "vocabulary.txt",
        "preprocessor_config.json",
    ]
    snapshot_download(
        settings.model_id,
        revision=settings.revision,
        local_dir=path,
        allow_patterns=allowed,
        token=False,
        max_workers=2,
    )
    hashes = {name: digest(path / name) for name in allowed if (path / name).is_file()}
    manifest = {"model_id": settings.model_id, "revision": settings.revision, "files": hashes}
    (path / "model.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return verify_model(state_dir, settings)
