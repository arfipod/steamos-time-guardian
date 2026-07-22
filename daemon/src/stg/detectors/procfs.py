"""Low-frequency procfs fallback for Steam environment variables.

This is intentionally secondary to Decky and Steam log events. It scans no faster than the
configured interval and reads only same-user processes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter, defaultdict
from pathlib import Path

from stg.models import GameIdentity

from .base import DetectorEvent, DetectorEventType

LOGGER = logging.getLogger("stg.detectors.procfs")
_ENV_KEYS = (b"SteamAppId", b"SteamGameId", b"STEAM_COMPAT_APP_ID")


class ProcfsDetector:
    def __init__(
        self,
        interval_seconds: int = 15,
        ignored_app_ids: set[str] | None = None,
        ignored_names: set[str] | None = None,
    ):
        self.interval_seconds = max(5, interval_seconds)
        self.ignored_app_ids = ignored_app_ids or set()
        self.ignored_names = {name.casefold() for name in (ignored_names or set())}
        self._stopped = False
        self._last: GameIdentity | None = None

    async def stop(self) -> None:
        self._stopped = True

    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None:
        while not self._stopped:
            try:
                detected = await asyncio.to_thread(self.scan)
                if self._key(detected) != self._key(self._last):
                    if self._last and detected:
                        await output.put(DetectorEvent(DetectorEventType.CHANGED, detected, "procfs_changed"))
                    elif detected:
                        await output.put(DetectorEvent(DetectorEventType.STARTED, detected, "procfs_detected"))
                    elif self._last:
                        await output.put(DetectorEvent(DetectorEventType.STOPPED, self._last, "procfs_disappeared"))
                    self._last = detected
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("procfs scan failed: %s", exc)
                await output.put(DetectorEvent(DetectorEventType.ERROR, reason=f"procfs: {exc}"))
            await asyncio.sleep(self.interval_seconds)

    @staticmethod
    def _key(game: GameIdentity | None) -> tuple[str | None, str] | None:
        return (game.app_id, game.name) if game else None

    def scan(self) -> GameIdentity | None:
        uid = os.getuid()
        grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            return None
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != uid:
                    continue
                raw = (entry / "environ").read_bytes()
                env: dict[bytes, bytes] = {}
                for item in raw.split(b"\x00"):
                    key, separator, value = item.partition(b"=")
                    if separator and key in _ENV_KEYS:
                        env[key] = value
                app_id = next((env[key].decode(errors="ignore") for key in _ENV_KEYS if env.get(key)), None)
                if not app_id or app_id in self.ignored_app_ids or app_id == "0":
                    continue
                comm = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
                grouped[app_id].append((int(entry.name), comm))
            except (OSError, ValueError):
                continue
        if not grouped:
            return None
        app_id, processes = max(grouped.items(), key=lambda item: (len(item[1]), item[0]))
        names = Counter(
            name for _, name in processes if name and name.casefold() not in self.ignored_names
        )
        name = names.most_common(1)[0][0] if names else f"Steam App {app_id}"
        return GameIdentity(
            app_id=app_id,
            name=name,
            source="procfs",
            pids=tuple(pid for pid, _ in processes),
            confidence=0.55,
        )
