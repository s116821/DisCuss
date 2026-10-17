"""Create a private, recognizable Windows interpreter image in a managed venv."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def create(venv: Path, base: Path) -> Path:
    scripts = venv / "Scripts"
    if not (venv / "pyvenv.cfg").is_file() or not scripts.is_dir():
        raise ValueError("Expected an existing private Windows virtual environment")
    # Copy the real interpreter, not the venv redirector (which starts a child).
    # The distinct suffix avoids Windows' case-insensitive discuss.exe CLI name.
    target = scripts / "DisCuss-Service.exe"
    for source, destination in [(base / "python.exe", target), *((p, scripts / p.name) for p in base.glob("*.dll"))]:
        if not destination.exists() or source.read_bytes() != destination.read_bytes():
            shutil.copy2(source, destination)
    return target


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("The named interpreter is for the native Windows installer")
    print(create(Path(sys.prefix), Path(sys.base_prefix)))


if __name__ == "__main__":
    main()
