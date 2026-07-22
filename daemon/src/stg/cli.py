"""Command-line and Desktop Mode entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .ipc import RpcError, UnixRpcClient
from .paths import AppPaths
from .service import run_service
from .tui import format_duration, run_tui
from .version import __version__


def parse_duration(value: str) -> int:
    text = value.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600}
    suffix = text[-1:] if text else ""
    if suffix in multipliers:
        number = text[:-1]
        multiplier = multipliers[suffix]
    else:
        number = text
        multiplier = 60
    try:
        seconds = int(number) * multiplier
    except ValueError as exc:
        raise argparse.ArgumentTypeError("duration must be an integer with optional s, m, or h") from exc
    if not -86400 <= seconds <= 86400:
        raise argparse.ArgumentTypeError("duration must be within ±24 hours")
    return seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steamos-time-guardian", description="Local SteamOS play-time guardian")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--socket", type=Path, help="override the Unix socket path")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    daemon = sub.add_parser("daemon", help="run the user daemon")
    daemon.add_argument("--simulation", action="store_true", help="force simulation detector")
    daemon.add_argument("--no-foreground-log", action="store_true", help="do not mirror JSON logs to stderr")

    sub.add_parser("status", help="show current status")
    sub.add_parser("diagnose", help="show a non-sensitive diagnostic snapshot")
    sub.add_parser("tui", help="open the Desktop Mode text UI")

    config = sub.add_parser("config", help="read or update configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show")
    patch = config_sub.add_parser("patch")
    patch.add_argument("json_patch", help="JSON object or @path/to/file.json")

    timer = sub.add_parser("timer", help="manage the session timer")
    timer_sub = timer.add_subparsers(dest="timer_command", required=True)
    timer_start = timer_sub.add_parser("start")
    timer_start.add_argument("duration", type=parse_duration)
    timer_start.add_argument(
        "--action",
        choices=("inherit", "notify_only", "soft", "close", "block"),
        help="override timer.default_action for this timer",
    )
    timer_sub.add_parser("pause")
    timer_sub.add_parser("resume")
    timer_sub.add_parser("cancel")
    timer_add = timer_sub.add_parser("add")
    timer_add.add_argument("duration", type=parse_duration)
    timer_remove = timer_sub.add_parser("remove")
    timer_remove.add_argument("duration", type=parse_duration)

    bonus = sub.add_parser("bonus", help="grant or remove exceptional daily time")
    bonus.add_argument("duration", type=parse_duration)
    bonus.add_argument("--reason", required=True)

    history = sub.add_parser("history", help="list, export, or clear history")
    history_sub = history.add_subparsers(dest="history_command", required=True)
    history_list = history_sub.add_parser("list")
    history_list.add_argument("--limit", type=int, default=50)
    history_list.add_argument("--day")
    history_export = history_sub.add_parser("export")
    history_export.add_argument("--format", choices=("json", "csv"), default="json")
    history_export.add_argument("--output", type=Path, required=True)
    history_clear = history_sub.add_parser("clear")
    history_clear.add_argument("--confirm", action="store_true")

    summary = sub.add_parser("summary", help="daily or weekly summaries")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    daily = summary_sub.add_parser("daily")
    daily.add_argument("--start-day")
    daily.add_argument("--days", type=int, default=1)
    weekly = summary_sub.add_parser("weekly")
    weekly.add_argument("--end-day")

    simulate = sub.add_parser("simulate", help="emit a simulator event")
    simulate.add_argument(
        "event",
        choices=(
            "game_started",
            "game_changed",
            "game_stopped",
            "suspend",
            "resume",
            "limit_reached",
            "close_success",
            "game_unresponsive",
            "service_restart_checkpoint",
        ),
    )
    simulate.add_argument("--app-id", default="999999")
    simulate.add_argument("--name", default="Simulated Game")
    return parser


async def _call(args: argparse.Namespace, method: str, params: dict[str, Any] | None = None) -> Any:
    socket_path = args.socket or AppPaths.from_environment().socket_file
    return await UnixRpcClient(socket_path).call(method, params)


def _load_patch(value: str) -> dict[str, Any]:
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("configuration patch must be a JSON object")
    return data


def _human_status(status: dict[str, Any]) -> str:
    game = status.get("game") or {}
    timer = status.get("timer", {})
    restriction = status.get("restriction", {})
    next_warning = status.get("next_warning") or {}
    lines = [
        f"Accounting day: {status.get('day_key')}",
        f"Played today: {format_duration(status.get('played_today_seconds'))}",
        f"Remaining today: {format_duration(status.get('remaining_today_seconds'))}",
        f"Game: {game.get('name', 'none')}",
        f"Timer: {timer.get('state')} ({format_duration(timer.get('remaining_seconds'))})",
        f"Restriction: level {restriction.get('effective_level')} ({restriction.get('reason')})",
        f"Next warning: {next_warning.get('scope', 'none')} / "
        f"{format_duration(next_warning.get('play_seconds_until'))}",
        f"Next reset: {format_duration(status.get('seconds_until_reset'))}",
    ]
    return "\n".join(lines)


def _print_result(result: Any, *, as_json: bool, command: str) -> None:
    if as_json or command not in {"status"}:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(_human_status(result))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "daemon":
            asyncio.run(
                run_service(
                    foreground=not args.no_foreground_log,
                    simulation=True if args.simulation else None,
                )
            )
            return 0
        if args.command == "tui":
            run_tui(args.socket)
            return 0
        method: str
        params: dict[str, Any] = {}
        if args.command == "status":
            method = "status.get"
        elif args.command == "diagnose":
            method = "diagnostics.get"
        elif args.command == "config":
            if args.config_command == "show":
                method = "config.get"
            else:
                method = "config.update"
                params = {"patch": _load_patch(args.json_patch)}
        elif args.command == "timer":
            method = f"timer.{args.timer_command}"
            if args.timer_command == "start":
                params = {"seconds": args.duration}
                if args.action is not None:
                    params["action"] = args.action
            elif args.timer_command == "add":
                method = "timer.adjust"
                params = {"seconds": abs(args.duration)}
            elif args.timer_command == "remove":
                method = "timer.adjust"
                params = {"seconds": -abs(args.duration)}
        elif args.command == "bonus":
            method = "daily.grant"
            params = {"seconds": args.duration, "reason": args.reason}
        elif args.command == "history":
            if args.history_command == "list":
                method = "history.list"
                params = {"limit": args.limit}
                if args.day:
                    params["day_key"] = args.day
            elif args.history_command == "export":
                result = asyncio.run(_call(args, "history.export", {"format": args.format}))
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(result["content"], encoding="utf-8")
                print(f"Exported {result['format']} history to {args.output}")
                return 0
            else:
                if not args.confirm:
                    parser.error("history clear requires --confirm")
                method = "history.clear"
                params = {"confirmation": "PURGE_HISTORY"}
        elif args.command == "summary":
            method = f"summary.{args.summary_command}"
            if args.summary_command == "daily":
                params = {"days": args.days}
                if args.start_day:
                    params["start_day"] = args.start_day
            elif args.end_day:
                params = {"end_day": args.end_day}
        elif args.command == "simulate":
            method = "simulation.emit"
            params = {"event": args.event, "app_id": args.app_id, "name": args.name}
        else:
            parser.error("unsupported command")
            return 2
        result = asyncio.run(_call(args, method, params))
        _print_result(result, as_json=args.json, command=args.command)
        return 0
    except (RpcError, ValueError, OSError, json.JSONDecodeError) as exc:
        message = exc.message if isinstance(exc, RpcError) else str(exc)
        print(f"error: {message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
