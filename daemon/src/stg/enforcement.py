"""Safe, replaceable restriction actions.

Tracking and policy live in the engine. This module contains the intentionally narrow side-effect
boundary for requesting a Steam close or signalling verified same-user game processes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from .models import GameIdentity

LOGGER = logging.getLogger("stg.enforcement")

PROTECTED_PROCESS_NAMES = {
    "systemd",
    "systemd --user",
    "steam",
    "steamwebhelper",
    "gamescope",
    "kwin_wayland",
    "plasmashell",
    "konsole",
    "sshd",
    "bash",
    "zsh",
    "fish",
    "python",
    "python3",
    "steamos-time-guardian",
}


@dataclass(frozen=True, slots=True)
class EnforcementPlan:
    level: int
    grace_seconds: int
    close_timeout_seconds: int
    request_steam_close: bool
    process_fallback: bool
    allow_force_kill: bool


class ProcessController(Protocol):
    async def terminate(self, game: GameIdentity, *, force: bool = False) -> list[int]: ...


class RecordingProcessController:
    """Test double and simulation backend."""

    def __init__(self):
        self.calls: list[tuple[GameIdentity, bool]] = []

    async def terminate(self, game: GameIdentity, *, force: bool = False) -> list[int]:
        self.calls.append((game, force))
        return list(game.pids)


class SafeProcessController:
    """Signals only verified same-UID processes associated with the expected Steam app ID."""

    def __init__(self, protected_names: set[str] | None = None):
        self.protected_names = protected_names or PROTECTED_PROCESS_NAMES
        self._protected_folded = {item.casefold() for item in self.protected_names}
        self.uid = os.getuid()

    async def terminate(self, game: GameIdentity, *, force: bool = False) -> list[int]:
        pids = await asyncio.to_thread(self._verified_pids, game)
        sent: list[int] = []
        chosen_signal = signal.SIGKILL if force else signal.SIGTERM
        for pid in pids:
            try:
                os.kill(pid, chosen_signal)
                sent.append(pid)
            except (ProcessLookupError, PermissionError, OSError) as exc:
                LOGGER.warning("could not signal pid %s: %s", pid, exc)
        return sent

    def _verified_pids(self, game: GameIdentity) -> list[int]:
        # Without a non-zero Steam App ID there is no sufficiently robust same-application
        # proof. Refuse the process fallback instead of trusting a name or arbitrary PID list.
        if not game.app_id or game.app_id == "0" or not game.app_id.isdigit():
            return []
        candidates = set(game.pids)
        candidates.update(self._scan_app_pids(game.app_id))
        current_pid = os.getpid()
        ancestors = self._ancestor_pids(current_pid)
        verified: list[int] = []
        for pid in sorted(candidates):
            if pid <= 1 or pid == current_pid or pid in ancestors:
                continue
            proc = Path("/proc") / str(pid)
            try:
                if proc.stat().st_uid != self.uid:
                    continue
                name = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip()
                if name.casefold() in self._protected_folded:
                    continue
                if not self._environment_matches(proc, game.app_id):
                    continue
                verified.append(pid)
            except OSError:
                continue
        return verified

    def _scan_app_pids(self, app_id: str) -> set[int]:
        result: set[int] = set()
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            return result
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid == self.uid and self._environment_matches(entry, app_id):
                    result.add(int(entry.name))
            except (OSError, ValueError):
                continue
        return result

    @staticmethod
    def _environment_matches(proc: Path, app_id: str) -> bool:
        raw = (proc / "environ").read_bytes()
        expected = app_id.encode()
        for item in raw.split(b"\x00"):
            key, separator, value = item.partition(b"=")
            if separator and key in {b"SteamAppId", b"SteamGameId", b"STEAM_COMPAT_APP_ID"} and value == expected:
                return True
        return False

    @staticmethod
    def _ancestor_pids(pid: int) -> set[int]:
        ancestors: set[int] = set()
        current = pid
        for _ in range(64):
            try:
                stat = (Path("/proc") / str(current) / "stat").read_text(encoding="utf-8")
                # comm may contain spaces inside parentheses; fields after the final ')' are stable.
                fields = stat.rsplit(")", 1)[1].strip().split()
                parent = int(fields[1])
            except (OSError, ValueError, IndexError):
                break
            if parent <= 1 or parent in ancestors:
                break
            ancestors.add(parent)
            current = parent
        return ancestors


def build_plan(config: dict[str, Any], level: int) -> EnforcementPlan:
    restriction = config["restriction"]
    return EnforcementPlan(
        level=level,
        grace_seconds=int(restriction["grace_seconds"]),
        close_timeout_seconds=int(restriction["close_timeout_seconds"]),
        request_steam_close=level >= 2,
        process_fallback=level >= 2 and bool(restriction["safe_process_fallback"]),
        allow_force_kill=level >= 2 and bool(restriction["force_kill_enabled"]),
    )


class EnforcementManager:
    """Schedules one cancellable enforcement flow at a time."""

    def __init__(
        self,
        controller: ProcessController,
        get_status: Callable[[], dict[str, Any]],
        record: Callable[[str, dict[str, Any], str], Awaitable[None]],
        plugin_is_recent: Callable[[], bool],
    ):
        self.controller = controller
        self.get_status = get_status
        self.record = record
        self.plugin_is_recent = plugin_is_recent
        self._task: asyncio.Task[None] | None = None
        self._generation = 0

    def cancel(self) -> None:
        self._generation += 1
        if self._task:
            self._task.cancel()
            self._task = None

    def arm(self, game: GameIdentity, config: dict[str, Any], level: int, reason: str, *, launch_block: bool = False) -> None:
        self.cancel()
        if level < 2:
            return
        self._generation += 1
        generation = self._generation
        plan = build_plan(config, level)
        delay = int(config["restriction"]["launch_grace_seconds"]) if launch_block else plan.grace_seconds
        self._task = asyncio.create_task(self._run(generation, game, plan, reason, delay))

    async def _run(
        self,
        generation: int,
        game: GameIdentity,
        plan: EnforcementPlan,
        reason: str,
        delay: int,
    ) -> None:
        try:
            if delay:
                await asyncio.sleep(delay)
            if not self._still_applicable(generation, game, plan.level):
                return
            request_payload = {
                "game": game.to_dict(),
                "reason": reason,
                "level": plan.level,
                "grace_elapsed": True,
            }
            if plan.request_steam_close:
                # ``record`` also publishes exactly one event to the Decky bridge.
                await self.record("enforcement.close_requested", request_payload, "warning")
            if plan.close_timeout_seconds:
                await asyncio.sleep(plan.close_timeout_seconds)
            if not self._still_applicable(generation, game, plan.level):
                return
            if plan.process_fallback:
                signalled = await self.controller.terminate(game, force=False)
                await self.record(
                    "enforcement.sigterm_attempted",
                    {"game": game.to_dict(), "pids": signalled, "plugin_recent": self.plugin_is_recent()},
                    "warning",
                )
                if plan.close_timeout_seconds:
                    await asyncio.sleep(plan.close_timeout_seconds)
            if not self._still_applicable(generation, game, plan.level):
                return
            if plan.allow_force_kill and plan.process_fallback:
                signalled = await self.controller.terminate(game, force=True)
                await self.record(
                    "enforcement.sigkill_attempted",
                    {"game": game.to_dict(), "pids": signalled},
                    "error",
                )
            else:
                await self.record(
                    "enforcement.game_still_running",
                    {"game": game.to_dict(), "force_kill_enabled": False},
                    "warning",
                )
        except asyncio.CancelledError:
            return
        finally:
            if generation == self._generation:
                self._task = None

    def _still_applicable(self, generation: int, game: GameIdentity, minimum_level: int) -> bool:
        if generation != self._generation:
            return False
        status = self.get_status()
        current = status.get("game")
        if not current:
            return False
        same = (
            current.get("app_id") == game.app_id
            if game.app_id
            else str(current.get("name", "")).casefold() == game.name.casefold()
        )
        return same and int(status["restriction"]["effective_level"]) >= minimum_level
