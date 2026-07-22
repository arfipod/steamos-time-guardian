"""Non-sensitive diagnostic snapshot generation."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

from .paths import AppPaths
from .storage import Storage
from .version import __version__


def _path_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    result: dict[str, Any] = {
        "exists": exists,
        "writable_parent": os.access(path if exists else path.parent, os.W_OK),
    }
    if exists:
        try:
            result["mode"] = stat.filemode(path.stat().st_mode)
            result["owner_uid"] = path.stat().st_uid
        except OSError as exc:
            result["error"] = str(exc)
    return result


def collect_diagnostics(
    paths: AppPaths,
    storage: Storage,
    status: dict[str, Any],
    *,
    detector_name: str,
    native_notifications_available: bool,
    plugin_recent: bool,
    config_recovery_note: str | None = None,
) -> dict[str, Any]:
    return {
        "project_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "uid": os.getuid(),
        "xdg_runtime_dir_set": bool(os.environ.get("XDG_RUNTIME_DIR")),
        "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown"),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
        "detector": detector_name,
        "decky_plugin_recent": plugin_recent,
        "native_notifications": {
            "notify_send_available": native_notifications_available,
            "dbus_session_bus_set": bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")),
        },
        "database": {
            "schema_version": storage.schema_version(),
            "quick_check": storage.quick_check(),
            "recovery_note": storage.recovery_note,
        },
        "configuration": {"recovery_note": config_recovery_note},
        "paths": {
            "config": _path_status(paths.config_file),
            "database": _path_status(paths.database_file),
            "log": _path_status(paths.log_file),
            "socket": _path_status(paths.socket_file),
        },
        "commands": {
            "systemctl": bool(shutil.which("systemctl")),
            "journalctl": bool(shutil.which("journalctl")),
            "notify_send": bool(shutil.which("notify-send")),
            "powerprofilesctl": bool(shutil.which("powerprofilesctl")),
        },
        "status": status,
        "recent_events": storage.list_events(limit=20),
    }
