"""Local setup/analytics commands; no Discord network activity."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .calendar import window_at
from .config import Config, ConfigError, load_config
from .reporting import render, standings
from .storage import Store
from .version import service_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discuss")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--version", action="version", version=service_version())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
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
        print(f"Setup required: {error}")
        return 2
    if args.command == "doctor":
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
                for page in render(window, standings(store, server.server_id, window, server.leaderboards)):
                    print(page)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
