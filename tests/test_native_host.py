from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from discuss.native_host import create


@pytest.mark.skipif(sys.platform != "win32", reason="Private Windows interpreter image")
def test_named_image_uses_venv_and_preserves_cli_without_redirect_child(tmp_path):
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    cli = venv / "Scripts" / "discuss.exe"
    cli.write_bytes(b"CLI sentinel")
    host = create(venv, Path(sys.base_prefix))
    result = subprocess.run(
        [
            str(host),
            "-c",
            "import ctypes,json,sys; b=ctypes.create_unicode_buffer(32768); "
            "ctypes.windll.kernel32.GetModuleFileNameW(None,b,len(b)); print(json.dumps([b.value,sys.prefix]))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image, prefix = json.loads(result.stdout)
    assert Path(image) == host and Path(prefix) == venv
    assert cli.read_bytes() == b"CLI sentinel"
    assert create(venv, Path(sys.base_prefix)) == host


def test_rejects_non_venv(tmp_path):
    with pytest.raises(ValueError, match="virtual environment"):
        create(tmp_path, Path(sys.base_prefix))
