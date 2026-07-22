#!/usr/bin/env python3
"""Generate a redacted support bundle without database, history, or game names."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from stg.ipc import RpcError, UnixRpcClient
from stg.paths import AppPaths
from stg.version import __version__


def redact(text: str) -> str:
    home = str(Path.home())
    username = os.environ.get("USER", "")
    result = text.replace(home, "$HOME")
    if username:
        result = re.sub(rf"\b{re.escape(username)}\b", "$USER", result)
    return result


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        return redact((result.stdout + result.stderr)[-50_000:])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}\n"


async def live_diagnostics(paths: AppPaths) -> dict[str, Any]:
    try:
        data = await UnixRpcClient(paths.socket_file).call("diagnostics.get")
        # Remove potentially identifying active game and event payloads.
        data.get("status", {}).pop("game", None)
        data.pop("recent_events", None)
        return data
    except RpcError as exc:
        return {"service_available": False, "error": exc.code}


def sanitized_config(paths: AppPaths) -> dict[str, Any]:
    try:
        data = json.loads(paths.config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False}
    detector = data.get("detector", {})
    if detector.get("steam_log_path") not in {None, "auto"}:
        detector["steam_log_path"] = "$REDACTED_PATH"
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = AppPaths.from_environment()
    generated = datetime.now(UTC).isoformat()
    files: dict[str, str] = {
        "manifest.json": json.dumps(
            {
                "bundle_schema": 1,
                "generated_at": generated,
                "project_version": __version__,
                "contains_history": False,
                "contains_database": False,
            },
            indent=2,
        ) + "\n",
        "diagnostics.json": json.dumps(asyncio.run(live_diagnostics(paths)), indent=2, sort_keys=True) + "\n",
        "config-sanitized.json": json.dumps(sanitized_config(paths), indent=2, sort_keys=True) + "\n",
        "platform.txt": redact(f"{platform.platform()}\nPython {platform.python_version()}\n"),
        "os-release.txt": command_output(["cat", "/etc/os-release"]),
        "systemd-status.txt": command_output(["systemctl", "--user", "status", "steamos-time-guardian.service", "--no-pager", "--full"]),
        "journal.txt": command_output(["journalctl", "--user", "-u", "steamos-time-guardian.service", "-n", "200", "--no-pager"]),
    }
    if paths.log_file.exists():
        try:
            lines = paths.log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
            files["daemon-log-tail.jsonl"] = redact("\n".join(lines) + "\n")
        except OSError:
            pass
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip():
            raise RuntimeError("support bundle verification failed")
    try:
        args.output.chmod(0o600)
    except OSError:
        pass
    print(f"Support bundle created: {args.output}")
    print("Excluded: SQLite database, session history, active game identity, credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
