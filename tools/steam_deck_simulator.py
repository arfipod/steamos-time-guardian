#!/usr/bin/env python3
"""Generate Steam Deck lifecycle scenarios through the public local IPC API."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from stg.ipc import UnixRpcClient
from stg.paths import AppPaths


async def emit(client: UnixRpcClient, event: str, **extra: Any) -> dict[str, Any]:
    return await client.call("simulation.emit", {"event": event, **extra})


async def run_scenario(client: UnixRpcClient, name: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if name == "normal-session":
        results.append(await emit(client, "game_started", app_id="424242", name="Simulated Deck Game"))
        results.append(await client.call("timer.start", {"seconds": 300, "action": "inherit"}))
        results.append(await emit(client, "suspend"))
        results.append(await emit(client, "resume"))
        results.append(await emit(client, "game_stopped"))
    elif name == "limit-and-close":
        results.append(await emit(client, "game_started", app_id="424243", name="Limit Scenario"))
        results.append(await emit(client, "limit_reached"))
        results.append(await emit(client, "close_success"))
    elif name == "unresponsive-game":
        results.append(await emit(client, "game_started", app_id="424244", name="Unresponsive Scenario"))
        results.append(await emit(client, "limit_reached"))
        results.append(await emit(client, "game_unresponsive"))
    elif name == "restart-checkpoint":
        results.append(await emit(client, "game_started", app_id="424245", name="Restart Scenario"))
        results.append(await emit(client, "service_restart_checkpoint"))
    else:
        raise ValueError(f"unknown scenario: {name}")
    return results


async def async_main(args: argparse.Namespace) -> int:
    client = UnixRpcClient(args.socket or AppPaths.from_environment().socket_file)
    if args.scenario:
        result: Any = await run_scenario(client, args.scenario)
    else:
        result = await emit(client, args.event, app_id=args.app_id, name=args.name)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scenario", choices=("normal-session", "limit-and-close", "unresponsive-game", "restart-checkpoint"))
    group.add_argument("--event", choices=("game_started", "game_changed", "game_stopped", "suspend", "resume", "limit_reached", "close_success", "game_unresponsive", "service_restart_checkpoint"))
    parser.add_argument("--app-id", default="999999")
    parser.add_argument("--name", default="Simulated Game")
    return asyncio.run(async_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
