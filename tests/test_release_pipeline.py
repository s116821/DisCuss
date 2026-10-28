"""Artifact handoff must preserve validated bytes and reject altered receipts."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from scripts.package_release import collect


def fixture(root: Path) -> None:
    for platform, suffix in (("linux-x64", "tar.gz"), ("windows-x64", "zip")):
        directory = root / f"build-{platform}"
        directory.mkdir(parents=True)
        wheel = directory / "discuss-1.1.1-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("discuss-1.1.1.dist-info/METADATA", "Version: 1.1.1\n")
        with tarfile.open(directory / "discuss-1.1.1.tar.gz", "w:gz") as archive:
            payload = b"Version: 1.1.1\n"
            member = tarfile.TarInfo("discuss-1.1.1/PKG-INFO")
            member.size = len(payload)
            archive.addfile(member, BytesIO(payload))
        (directory / f"DisCuss-v1.1.1-{platform}.{suffix}").write_bytes(b"validated native fixture")
        (directory / "SHA256SUMS").write_text("validated checksum fixture\n")
        receipt = {
            "source_commit": "abc",
            "tag": "v1.1.1",
            "platform": platform,
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()},
        }
        (directory / "build-receipt.json").write_text(json.dumps(receipt))


def test_collection_preserves_saved_bytes(tmp_path: Path) -> None:
    source, output = tmp_path / "saved", tmp_path / "dist"
    fixture(source)
    collect(source, output, "v1.1.1", "abc")
    assert len(list(output.iterdir())) == 5
    for path in output.iterdir():
        if path.name != "SHA256SUMS":
            platform = "windows-x64" if path.suffix == ".zip" else "linux-x64"
            assert path.read_bytes() == (source / f"build-{platform}" / path.name).read_bytes()


@pytest.mark.parametrize("damage", ["source", "version", "checksum", "extra", "metadata"])
def test_collection_rejects_invalid_handoff(tmp_path: Path, damage: str) -> None:
    source = tmp_path / "saved"
    fixture(source)
    directory = source / "build-windows-x64"
    receipt_path = directory / "build-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if damage == "source":
        receipt["source_commit"] = "def"
    elif damage == "version":
        receipt["tag"] = "v1.1.2"
    elif damage == "extra":
        (directory / "unexpected.txt").write_text("unrecorded")
    else:
        wheel = next(directory.glob("*.whl"))
        if damage == "checksum":
            wheel.write_bytes(b"tampered")
        else:
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("discuss-1.1.1.dist-info/METADATA", "Version: 9.9.9\n")
            receipt["files"][wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        collect(source, tmp_path / "dist", "v1.1.1", "abc")
    assert not (tmp_path / "dist").exists()
