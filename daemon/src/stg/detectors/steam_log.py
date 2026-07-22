"""Event-oriented parser and follower for Steam's gameprocess_log.txt.

Steam's log format is not a stable public API, so this adapter is isolated, fixture-tested,
and allowed to fail without taking down the daemon.
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.util
import logging
import os
import re
import struct
from pathlib import Path
from typing import BinaryIO

from stg.models import GameIdentity

from .base import DetectorEvent, DetectorEventType

LOGGER = logging.getLogger("stg.detectors.steam_log")

_TRACK_RE = re.compile(r"AppID\s+(?P<app>\d+)\s+adding PID\s+(?P<pid>\d+)\s+as a tracked process", re.I)
_UNTRACK_RE = re.compile(r"AppID\s+(?P<app>\d+)\s+no longer tracking PID\s+(?P<pid>\d+)", re.I)
_REMOVE_RE = re.compile(r"Remove\s+(?P<app>\d+)\s+from running list", re.I)
_NAME_RE = re.compile(r"AppID\s+(?P<app>\d+).*?\b(?:name|game)\b[=:]\s*['\"]?(?P<name>[^'\"]+)", re.I)

# Linux inotify constants. Watching the directory also catches log rotation/recreation.
_IN_MODIFY = 0x00000002
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_EVENT_HEADER = struct.Struct("iIII")


class SteamLogParser:
    def __init__(self, names: dict[str, str] | None = None):
        self.pids: dict[str, set[int]] = {}
        self.names = names or {}

    def feed_line(self, line: str) -> list[DetectorEvent]:
        events: list[DetectorEvent] = []
        if match := _NAME_RE.search(line):
            self.names[match["app"]] = match["name"].strip()
        if match := _TRACK_RE.search(line):
            app_id = match["app"]
            pid = int(match["pid"])
            current = self.pids.setdefault(app_id, set())
            first = not current
            current.add(pid)
            if first:
                events.append(
                    DetectorEvent(
                        DetectorEventType.STARTED,
                        self._identity(app_id),
                        reason="steam_log_first_tracked_process",
                    )
                )
            return events
        if match := _UNTRACK_RE.search(line):
            app_id = match["app"]
            pid = int(match["pid"])
            current = self.pids.get(app_id)
            if current is not None:
                current.discard(pid)
            return events
        if match := _REMOVE_RE.search(line):
            app_id = match["app"]
            identity = self._identity(app_id)
            self.pids.pop(app_id, None)
            events.append(
                DetectorEvent(
                    DetectorEventType.STOPPED,
                    identity,
                    reason="steam_log_removed_from_running_list",
                )
            )
        return events

    def _identity(self, app_id: str) -> GameIdentity:
        return GameIdentity(
            app_id=app_id,
            name=self.names.get(app_id, f"Steam App {app_id}"),
            source="steam_log",
            pids=tuple(sorted(self.pids.get(app_id, set()))),
            confidence=0.85,
        )


def discover_steam_log(explicit: str = "auto") -> Path | None:
    if explicit != "auto":
        return Path(explicit).expanduser()
    home = Path.home()
    candidates = (
        home / ".local/share/Steam/logs/gameprocess_log.txt",
        home / ".steam/steam/logs/gameprocess_log.txt",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/logs/gameprocess_log.txt",
    )
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def load_app_names() -> dict[str, str]:
    """Best-effort parse of installed app manifests; never required for detection."""
    roots = (
        Path.home() / ".local/share/Steam/steamapps",
        Path.home() / ".steam/steam/steamapps",
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps",
    )
    app_re = re.compile(r'^\s*"appid"\s+"(?P<value>\d+)"', re.I)
    name_re = re.compile(r'^\s*"name"\s+"(?P<value>.*)"', re.I)
    names: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for manifest in root.glob("appmanifest_*.acf"):
            app_id = None
            name = None
            try:
                for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
                    if app_id is None and (match := app_re.match(line)):
                        app_id = match["value"]
                    elif name is None and (match := name_re.match(line)):
                        name = match["value"]
                    if app_id and name:
                        names[app_id] = name
                        break
            except OSError:
                continue
    return names


class SteamLogDetector:
    def __init__(self, path: Path | None):
        self.path = path
        self.parser = SteamLogParser(load_app_names())
        self._stopped = False
        self._wake = asyncio.Event()
        self._inotify_fd: int | None = None

    async def stop(self) -> None:
        self._stopped = True
        self._wake.set()
        if self._inotify_fd is not None:
            try:
                os.close(self._inotify_fd)
            except OSError:
                pass
            self._inotify_fd = None

    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None:
        if self.path is None:
            return
        handle: BinaryIO | None = None
        loop = asyncio.get_running_loop()
        try:
            handle = self._open_at_end()
            self._inotify_fd = self._setup_inotify()
            if self._inotify_fd is not None:
                loop.add_reader(self._inotify_fd, self._on_inotify)
            while not self._stopped:
                await self._wake_or_timeout(5.0 if self._inotify_fd is None else 300.0)
                self._wake.clear()
                if handle is None or not self.path.exists() or self.path.stat().st_ino != os.fstat(handle.fileno()).st_ino:
                    if handle:
                        handle.close()
                    handle = self._open_at_end()
                if handle:
                    for raw in handle.readlines():
                        line = raw.decode("utf-8", errors="replace")
                        for event in self.parser.feed_line(line):
                            await output.put(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # isolated adapter: report and stop, do not crash daemon
            LOGGER.exception("Steam log detector stopped")
            await output.put(DetectorEvent(DetectorEventType.ERROR, reason=f"steam_log: {exc}"))
        finally:
            if self._inotify_fd is not None:
                try:
                    loop.remove_reader(self._inotify_fd)
                except Exception:
                    pass
            if handle:
                handle.close()

    def _open_at_end(self) -> BinaryIO | None:
        try:
            handle = self.path.open("rb") if self.path else None
            if handle:
                handle.seek(0, os.SEEK_END)
            return handle
        except OSError:
            return None

    async def _wake_or_timeout(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=timeout)
        except TimeoutError:
            return

    def _on_inotify(self) -> None:
        if self._inotify_fd is None:
            return
        try:
            data = os.read(self._inotify_fd, 64 * 1024)
            offset = 0
            while offset + _EVENT_HEADER.size <= len(data):
                _, mask, _, length = _EVENT_HEADER.unpack_from(data, offset)
                offset += _EVENT_HEADER.size + length
                if mask & (_IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE_SELF | _IN_MOVE_SELF):
                    self._wake.set()
        except BlockingIOError:
            pass
        except OSError:
            self._wake.set()

    def _setup_inotify(self) -> int | None:
        libc_name = ctypes.util.find_library("c")
        if not libc_name or not self.path:
            return None
        try:
            libc = ctypes.CDLL(libc_name, use_errno=True)
            init = libc.inotify_init1
            init.argtypes = [ctypes.c_int]
            init.restype = ctypes.c_int
            add_watch = libc.inotify_add_watch
            add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
            add_watch.restype = ctypes.c_int
            fd = init(os.O_NONBLOCK | os.O_CLOEXEC)
            if fd < 0:
                return None
            mask = _IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE_SELF | _IN_MOVE_SELF
            watch = add_watch(fd, os.fsencode(self.path.parent), mask)
            if watch < 0:
                os.close(fd)
                return None
            return fd
        except (AttributeError, OSError):
            return None
