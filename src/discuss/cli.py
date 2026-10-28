"""Local setup/analytics commands; no Discord network activity."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .calendar import window_at
from .config import Config, ConfigError, Transcription, check_private_file, load_config
from .reporting import render, standings
from .service_logging import ServiceLogging
from .storage import Store
from .version import service_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discuss")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--log-file", type=Path, help="Protected local boot/diagnostic log")
    parser.add_argument("--version", action="version", version=service_version())
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument(
        "--runtime", action="store_true", help="Validate cached model/native runtime without Discord access"
    )
    commands.add_parser("run")
    status = commands.add_parser("status")
    status.add_argument("--state-dir", type=Path, required=True)
    setup = commands.add_parser("model-setup")
    setup.add_argument("--state-dir", type=Path, help="External state/model cache, usable before bot token setup")
    schema = commands.add_parser("schema")
    schema.add_argument("--output", type=Path)
    board = commands.add_parser("standings")
    board.add_argument("--server", required=True)
    board.add_argument("--period", choices=["day", "week", "month", "year"], default="week")
    delete = commands.add_parser("delete-member")
    delete.add_argument("--server", required=True)
    delete.add_argument("--member", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            with ServiceLogging(args.log_file) as session:
                return _execute(args, session)
        except (ConfigError, OSError):
            print("Setup required: diagnostic log path must be writable and protected.")
            return 0 if args.command == "run" else 2
    return _execute(args)


def _execute(args: argparse.Namespace, session: ServiceLogging | None = None) -> int:
    if args.command == "status":
        try:
            path = args.state_dir / "health.json"
            check_private_file(path)
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            age = (datetime.now(UTC) - datetime.fromisoformat(snapshot["updated_at"])).total_seconds()
            snapshot["stale"] = age > 30
            print(json.dumps(snapshot, indent=2))
            return 0 if snapshot["running"] and age <= 30 else 1
        except (OSError, ValueError, KeyError):
            print("No readable protected runtime health snapshot; check service/task and log.")
            return 2
    if args.command == "model-setup":
        try:
            from .models import prepare_model

            data = {}
            if args.config.is_file():
                check_private_file(args.config)
                data = json.loads(args.config.read_text(encoding="utf-8-sig"))
            settings = Transcription.model_validate_json(json.dumps(data.get("transcription", {})))
            root = args.state_dir or Path(data.get("state_dir", "state"))
            if not root.is_absolute():
                root = args.config.resolve().parent / root
            prepare_model(root, settings)
            print("Pinned local speech model prepared and verified.")
            return 0
        except (ImportError, OSError, ValueError):
            print("Model setup requires runtime dependencies, valid speech settings and network access; retry setup.")
            return 2
    if args.command == "schema":
        text = json.dumps(Config.model_json_schema(), indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    try:
        config = load_config(args.config)
    except ConfigError as error:
        if args.command == "run":
            logging.getLogger(__name__).error("configuration_invalid", exc_info=True)
            print("Setup required: validate the protected configuration with discuss doctor.")
            return 0
        print(f"Setup required: {error}")
        return 0 if args.command == "run" else 2
    if args.command == "run":
        try:
            from .application import run_application, state_path

            if session:
                session.configure(config, state_path(config, args.config))
            logging.getLogger(__name__).info(
                "service_starting",
                extra={
                    "configured_level": config.logging.level,
                    "version": service_version(),
                },
            )
            return run_application(config, args.config)
        except (ConfigError, ImportError):
            logging.getLogger(__name__).error("runtime_setup_required", exc_info=True)
            print("Setup required: verify protected config, runtime dependencies and the prepared speech model.")
            return 0
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("service_interrupted")
            return 0
        except Exception:
            logging.getLogger(__name__).error("service_failed", exc_info=True)
            return 1
    if args.command == "doctor":
        if args.runtime:
            try:
                from discord.opus import Decoder

                from .application import state_path
                from .speech import LocalTranscriber

                Decoder()
                LocalTranscriber(state_path(config, args.config), config.transcription)
            except (ImportError, ConfigError, RuntimeError):
                print("Runtime setup required: install dependencies/native Opus and prepare the local model.")
                return 2
        print(
            f"Configuration ready: {len(config.bots)} bot identities; {len(config.servers)} server policies. "
            "Offline preflight only; Discord connectivity, receiver and speech readiness are separate checks."
        )
        return 0
    state_dir = Path(config.state_dir)
    if not state_dir.is_absolute():
        state_dir = args.config.resolve().parent / state_dir
    store = Store(state_dir / "statistics.sqlite3")
    try:
        if args.command == "backup":
            store.backup(args.destination)
        else:
            server = next((s for s in config.servers if s.server_id == args.server), None)
            if server is None:
                print("Unknown configured server")
                return 2
            if args.command == "delete-member":
                store.delete_member(server.server_id, args.member)
                print("Local member data deleted; previously posted Discord messages require operator removal.")
            else:
                window = window_at(datetime.now(UTC), server.leaderboards.timezone, args.period)
                for page in render(
                    window,
                    standings(store, server.server_id, window, server.leaderboards),
                    timezone=server.leaderboards.timezone,
                    show_scaled=server.leaderboards.scaled.enabled,
                ):
                    print(page)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
