"""Privileged installer acceptance on disposable GitHub-hosted runners only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def smoke(
    assets: Path,
    upgrade: Path | None = None,
    second_upgrade: Path | None = None,
    *,
    tag: str = "v1.2.3",
) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("Privileged smoke is restricted to disposable GitHub-hosted runners")
    windows = os.name == "nt"
    root = Path(os.environ["ProgramData"]) / "DisCuss-CI" if windows else Path("/opt/discuss")
    if root.exists():
        raise RuntimeError("Smoke root must be clean; no existing install may be overwritten")

    with tempfile.TemporaryDirectory() as temporary:
        extract = Path(temporary)

        def unpack(directory: Path, version: str, name: str) -> Path:
            target = extract / name
            target.mkdir()
            platform = "windows-x64.zip" if windows else "linux-x64.tar.gz"
            archive = directory / f"DisCuss-{version}-{platform}"
            if windows:
                with zipfile.ZipFile(archive) as reader:
                    reader.extractall(target)
            else:
                with tarfile.open(archive) as reader:
                    reader.extractall(target, filter="data")
            return target

        first = unpack(assets, tag, "first")

        def install(bundle: Path, operation: str = "install", *, fail: bool = False) -> None:
            if windows:
                args = [
                    "pwsh",
                    "-File",
                    str(bundle / "install.ps1"),
                    "-Root",
                    str(root),
                    "-TaskName",
                    "DisCuss-CI",
                    "-Operation",
                    operation,
                ]
            else:
                args = ["sudo", "bash", str(bundle / "install.sh"), "--root", str(root), "--operation", operation]
            if fail:
                assert subprocess.run(args).returncode != 0
            else:
                run(*args)

        def admin_python(code: str) -> None:
            # Linux install metadata is operator-only; read it as root too.
            if windows:
                python = json.loads((root / "current.json").read_text(encoding="utf-8-sig"))["python"]
                run(python, "-c", code, str(root))
            else:
                command = (
                    'import json,subprocess,sys; p=json.load(open(sys.argv[1]+"/current.json"))["python"]; '
                    'subprocess.run([p,"-c",sys.argv[2],sys.argv[1]],check=True)'
                )
                run("sudo", "python3", "-c", command, str(root), code)

        install(first)
        admin_python(
            "import json,pathlib,subprocess,sys; r=pathlib.Path(sys.argv[1]); "
            'p=json.load(open(r/"current.json",encoding="utf-8-sig"))["python"]; '
            'assert subprocess.run([p,"-m","discuss.cli","--config",str(r/"config.json"),"run"]).returncode==0'
        )
        if windows:
            run(
                "pwsh",
                "-Command",
                "$t=Get-ScheduledTask -TaskName DisCuss-CI; if($t.Principal.LogonType -ne 'ServiceAccount' "
                "-or $t.Settings.ExecutionTimeLimit -ne 'PT0S' -or $t.Settings.MultipleInstances -ne 'IgnoreNew' "
                "-or $t.Triggers.CimClass.CimClassName -notcontains 'MSFT_TaskBootTrigger')"
                "{throw 'Startup task contract failed'}",
            )
        else:
            run("sudo", "systemctl", "is-enabled", "discuss.service")
            run("sudo", "systemd-analyze", "verify", "/etc/systemd/system/discuss.service")
        # Setup exits before Discord login; preserve an unrelated original SQLite
        # schema to prove installer backup never imports application migrations.
        admin_python(
            "import pathlib,sqlite3,sys; r=pathlib.Path(sys.argv[1]); "
            'd=sqlite3.connect(r/"state/statistics.sqlite3"); d.execute("CREATE TABLE sentinel(value TEXT)"); '
            "d.execute(\"INSERT INTO sentinel VALUES ('preserve')\"); d.commit(); d.close()"
        )
        install(first)
        broken = extract / "broken"
        shutil.copytree(first, broken)
        (broken / "runtime-requirements.txt").write_text("invalid dependency syntax !!!\n")
        manifest = json.loads((broken / "manifest.json").read_text())
        manifest.update(tag="v1.2.99", version="1.2.99")
        manifest["files"]["runtime-requirements.txt"] = hashlib.sha256(
            (broken / "runtime-requirements.txt").read_bytes()
        ).hexdigest()
        (broken / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (broken / "BUNDLE_SHA256SUMS").write_text(
            "".join(
                f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                for p in sorted(broken.iterdir())
                if p.name != "BUNDLE_SHA256SUMS"
            )
        )
        install(broken, fail=True)
        if upgrade is not None:
            second = unpack(upgrade, "v1.2.4", "second")
            install(second)
            if second_upgrade is not None:
                third = unpack(second_upgrade, "v1.2.5", "third")
                install(third)
            install(second, "rollback")
        admin_python(
            'import pathlib,sqlite3,sys; r=pathlib.Path(sys.argv[1]); d=sqlite3.connect(r/"state/statistics.sqlite3"); '
            'assert d.execute("SELECT value FROM sentinel").fetchall()==[("preserve",)]; '
            'assert list((r/"backups").glob("*/statistics.sqlite3")); d.close()'
        )
        install(first, "uninstall")
        admin_python(
            "import pathlib,sys; r=pathlib.Path(sys.argv[1]); "
            'assert (r/"config.json").is_file() and (r/"state/statistics.sqlite3").is_file()'
        )
    print("Extracted assets: install, startup, setup exit, rerun, SQLite preservation and removal passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--upgrade", type=Path)
    parser.add_argument("--second-upgrade", type=Path)
    parser.add_argument("--tag", default="v1.2.3")
    args = parser.parse_args()
    smoke(
        args.assets.resolve(),
        args.upgrade.resolve() if args.upgrade else None,
        args.second_upgrade.resolve() if args.second_upgrade else None,
        tag=args.tag,
    )
