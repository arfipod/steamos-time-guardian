"""Daemon orchestration: detector, engine, IPC, notifications, and enforcement."""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import signal
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from .clock import SystemClock
from .config import ConfigStore
from .detectors.base import DetectorEvent, DetectorEventType
from .detectors.composite import CompositeDetector
from .detectors.disabled import DisabledDetector
from .detectors.procfs import ProcfsDetector
from .detectors.simulation import SimulationDetector
from .detectors.steam_log import SteamLogDetector, discover_steam_log
from .diagnostics import collect_diagnostics
from .enforcement import EnforcementManager, SafeProcessController
from .engine import DomainError, GuardianEngine
from .events import EventBus
from .ipc import RpcError, UnixRpcServer
from .logging_setup import configure_logging
from .models import DomainEvent, GameIdentity, TimerState
from .notifications import NativeNotifier, Notification
from .paths import AppPaths
from .storage import DatabaseError, Storage
from .version import __version__

LOGGER = logging.getLogger("stg.service")


class GuardianService:
    def __init__(
        self,
        paths: AppPaths | None = None,
        *,
        foreground: bool = False,
        simulation_override: bool | None = None,
    ):
        self.paths = paths or AppPaths.from_environment()
        self.paths.ensure()
        self.config_store = ConfigStore(self.paths.config_file)
        self.config = self.config_store.load()
        if simulation_override is not None:
            self.config["simulation"]["enabled"] = simulation_override
        self.simulation_enabled = (
            bool(self.config["simulation"]["enabled"])
            if simulation_override is not None
            else bool(self.config["simulation"]["enabled"] or os.environ.get("STG_SIMULATION") == "1")
        )
        configure_logging(
            self.paths.log_file,
            self.config["logging"]["level"],
            self.config["logging"]["max_bytes"],
            self.config["logging"]["backup_count"],
            foreground=foreground,
        )
        self.storage = Storage(
            self.paths.database_file,
            backup_count=self.config["history"]["backup_count"],
        )
        self.storage.open()
        self.clock = SystemClock()
        self.engine = GuardianEngine(self.storage, self.config, self.clock)
        self.event_bus = EventBus()
        self.notifier = NativeNotifier(self.config["warnings"]["native_desktop_notifications"])
        self.rpc = UnixRpcServer(self.paths.socket_file, self.handle_rpc, self.event_bus)
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._tick_wake = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._last_plugin_heartbeat = float("-inf")
        self._last_decky_signal = float("-inf")
        self.simulation_detector: SimulationDetector | None = None
        self.detector = self._build_detector()
        self.detector_name = ",".join(type(item).__name__ for item in self.detector.detectors)
        self.enforcement = EnforcementManager(
            SafeProcessController(),
            self.engine.status,
            self._record_side_effect_event,
            self.plugin_is_recent,
        )
        self._started = False

    def _build_detector(self) -> CompositeDetector:
        detector_config = self.config["detector"]
        if self.simulation_enabled:
            self.simulation_detector = SimulationDetector()
            return CompositeDetector([self.simulation_detector])
        mode = detector_config["mode"]
        if mode == "disabled":
            return CompositeDetector([DisabledDetector()])
        detectors = []
        if mode in {"auto", "steam_log"}:
            detectors.append(SteamLogDetector(discover_steam_log(detector_config["steam_log_path"])))
        if mode in {"auto", "procfs"}:
            detectors.append(
                ProcfsDetector(
                    detector_config["procfs_fallback_interval_seconds"],
                    set(detector_config["ignored_app_ids"]),
                    set(detector_config["ignored_names"]),
                )
            )
        if not detectors:
            detectors.append(DisabledDetector())
        return CompositeDetector(detectors)

    async def start(self) -> None:
        if self._started:
            return
        await self.rpc.start()
        self._started = True
        await self._dispatch_many(self.engine.take_initial_events())
        await self._record_side_effect_event(
            "service.started",
            {"version": __version__, "detector": self.detector_name, "socket": str(self.paths.socket_file)},
            "info",
        )
        detector_queue: asyncio.Queue[DetectorEvent] = asyncio.Queue()
        self._tasks = [
            asyncio.create_task(self.detector.run(detector_queue), name="detector"),
            asyncio.create_task(self._consume_detector(detector_queue), name="detector-consumer"),
            asyncio.create_task(self._tick_loop(), name="tick-loop"),
        ]
        LOGGER.info("service started", extra={"event": "service.started"})

    async def stop(self) -> None:
        if not self._started:
            return
        self._stop_event.set()
        self.enforcement.cancel()
        await self.detector.stop()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                LOGGER.exception("background task failed during shutdown")
        async with self._lock:
            events = self.engine.shutdown()
        await self._dispatch_many(events)
        await self._record_side_effect_event("service.stopped", {}, "info")
        await self.rpc.close()
        self.storage.close()
        self._started = False

    async def wait(self) -> None:
        await self._stop_event.wait()

    def request_stop(self) -> None:
        self._stop_event.set()

    def plugin_is_recent(self) -> bool:
        ttl = self.config["detector"]["decky_signal_ttl_seconds"]
        return self.clock.monotonic() - self._last_plugin_heartbeat <= ttl

    def decky_signal_is_recent(self) -> bool:
        ttl = self.config["detector"]["decky_signal_ttl_seconds"]
        return self.clock.monotonic() - self._last_decky_signal <= ttl

    async def handle_rpc(self, method: str, params: dict[str, Any]) -> Any:
        if method == "service.ping":
            return {"ok": True, "version": __version__, "pid": os.getpid()}
        if method in {"status", "status.get"}:
            async with self._lock:
                events = self.engine.tick()
                result = self.engine.status()
            await self._dispatch_many(events)
            return result
        if method == "config.get":
            return copy.deepcopy(self.config)
        if method == "config.update":
            patch = self._require_dict(params, "patch")
            async with self._lock:
                self.config = self.config_store.update(patch, self.config)
                events = self.engine.update_config(self.config)
                self.notifier.enabled = self.config["warnings"]["native_desktop_notifications"]
            await self._dispatch_many(events)
            self._tick_wake.set()
            return {
                "config": copy.deepcopy(self.config),
                "restart_recommended": any(key in patch for key in ("detector", "logging", "simulation")),
            }
        if method == "timer.start":
            seconds = self._require_int(params, "seconds", 60, 86400)
            raw_action = params.get("action")
            action = (
                self.config["timer"]["default_action"]
                if raw_action is None
                else self._require_text(params, "action", 1, 32)
            )
            return await self._engine_action(lambda: self.engine.start_timer(seconds, action))
        if method == "timer.pause":
            return await self._engine_action(self.engine.pause_timer)
        if method == "timer.resume":
            return await self._engine_action(self.engine.resume_timer)
        if method == "timer.cancel":
            return await self._engine_action(self.engine.cancel_timer)
        if method == "timer.adjust":
            seconds = self._require_int(params, "seconds", -86400, 86400)
            return await self._engine_action(lambda: self.engine.adjust_timer(seconds))
        if method == "daily.grant":
            seconds = self._require_int(params, "seconds", -86400, 86400)
            reason = self._require_text(params, "reason", 1, 200)
            return await self._engine_action(lambda: self.engine.grant_daily_time(seconds, reason))
        if method == "history.list":
            limit = self._require_int(params, "limit", 1, 1000, default=100)
            day_key = params.get("day_key")
            if day_key is not None:
                day_key = self._validate_day_key(str(day_key))
            return {"sessions": self.storage.list_sessions(limit, day_key)}
        if method == "history.events":
            limit = self._require_int(params, "limit", 1, 1000, default=100)
            return {"events": self.storage.list_events(limit)}
        if method == "history.clear":
            if params.get("confirmation") != "PURGE_HISTORY":
                raise RpcError("confirmation_required", "confirmation must be PURGE_HISTORY")
            try:
                async with self._lock:
                    self.storage.clear_history()
                    self.engine.played_today = 0.0
            except DatabaseError as exc:
                raise RpcError("invalid_state", str(exc)) from exc
            await self._record_side_effect_event("history.cleared", {}, "warning")
            return {"cleared": True}
        if method == "history.export":
            format_name = str(params.get("format", "json"))
            return {"format": format_name, "content": self.storage.export(format_name)}
        if method == "summary.daily":
            day_text = str(params.get("start_day", self.engine.day_key))
            start = date.fromisoformat(self._validate_day_key(day_text))
            days = self._require_int(params, "days", 1, 366, default=1)
            return {"days": self.storage.daily_summary(start, days)}
        if method == "summary.weekly":
            day_text = str(params.get("end_day", self.engine.day_key))
            end = date.fromisoformat(self._validate_day_key(day_text))
            return self.storage.weekly_summary(end)
        if method == "diagnostics.get":
            async with self._lock:
                status = self.engine.status()
            return collect_diagnostics(
                self.paths,
                self.storage,
                status,
                detector_name=self.detector_name,
                native_notifications_available=self.notifier.available,
                plugin_recent=self.plugin_is_recent(),
                config_recovery_note=self.config_store.last_recovery,
            )
        if method == "plugin.heartbeat":
            self._last_plugin_heartbeat = self.clock.monotonic()
            return {"ok": True, "detector_signal_ttl_seconds": self.config["detector"]["decky_signal_ttl_seconds"]}
        if method == "detector.report_foreground":
            return await self._report_foreground(params)
        if method == "detector.report_lifetime":
            self._last_plugin_heartbeat = self.clock.monotonic()
            payload = {
                "app_id": self._optional_app_id(params.get("app_id")),
                "running": self._require_bool(params, "running"),
                "instance_id": str(
                    self._require_int(params, "instance_id", 0, 2**63 - 1, default=0)
                ),
            }
            await self._record_side_effect_event("decky.app_lifetime", payload, "info")
            return {"accepted": True}
        if method == "enforcement.report_result":
            self._last_plugin_heartbeat = self.clock.monotonic()
            payload = {
                "app_id": self._optional_app_id(params.get("app_id")),
                "success": self._require_bool(params, "success"),
                "detail": str(params.get("detail", ""))[:300],
            }
            await self._record_side_effect_event("enforcement.plugin_result", payload, "info")
            return {"accepted": True}
        if method == "simulation.emit":
            if not self.simulation_enabled:
                raise RpcError("simulation_disabled", "simulation mode is not enabled")
            return await self._simulation_emit(params)
        raise RpcError("method_not_found", f"unknown method: {method}")

    async def _engine_action(self, action: Callable[[], list[DomainEvent]]) -> dict[str, Any]:
        error: DomainError | None = None
        async with self._lock:
            # Account and publish elapsed-time effects even when the requested state transition
            # is invalid. Engine actions call tick again, but the second delta is zero.
            events = self.engine.tick()
            try:
                events.extend(action())
            except DomainError as exc:
                error = exc
            status = self.engine.status()
        await self._dispatch_many(events)
        self._tick_wake.set()
        if error is not None:
            raise RpcError("invalid_state", str(error)) from error
        return {"status": status}

    async def _report_foreground(self, params: dict[str, Any]) -> dict[str, Any]:
        self._last_plugin_heartbeat = self.clock.monotonic()
        self._last_decky_signal = self.clock.monotonic()
        running = self._require_bool(params, "running", default=True)
        try:
            async with self._lock:
                if not running:
                    events = self.engine.stop_game(reason="decky_foreground_cleared")
                else:
                    app_id = self._optional_app_id(params.get("app_id"))
                    name = self._require_text(params, "name", 1, 200)
                    pids = self._require_pids(params.get("pids", []))
                    game = GameIdentity(
                        app_id=app_id,
                        name=name,
                        source="decky",
                        pids=pids,
                        confidence=1.0,
                        instance_id=str(params.get("instance_id"))[:64] if params.get("instance_id") is not None else None,
                    )
                    events = self.engine.set_game(game, reason="decky_foreground")
                status = self.engine.status()
        except DomainError as exc:
            raise RpcError("invalid_state", str(exc)) from exc
        await self._dispatch_many(events)
        self._tick_wake.set()
        return {"accepted": True, "status": status}

    async def _simulation_emit(self, params: dict[str, Any]) -> dict[str, Any]:
        event_name = self._require_text(params, "event", 1, 64)
        if event_name in {"game_started", "game_changed"}:
            game = GameIdentity(
                app_id=self._optional_app_id(params.get("app_id", "999999")),
                name=self._require_text(params, "name", 1, 200)
                if "name" in params
                else "Simulated Game",
                source="simulation",
                pids=self._require_pids(params.get("pids", [])),
                confidence=1.0,
            )
            events = await self._engine_action(lambda: self.engine.set_game(game, reason=event_name))
            return {"emitted": event_name, **events}
        if event_name in {"game_stopped", "close_success"}:
            result = await self._engine_action(
                lambda: self.engine.stop_game(reason="controlled_close" if event_name == "close_success" else "simulated_exit")
            )
            return {"emitted": event_name, **result}
        if event_name == "suspend":
            result = await self._engine_action(lambda: self.engine.suspend("simulation"))
            return {"emitted": event_name, **result}
        if event_name == "resume":
            result = await self._engine_action(lambda: self.engine.resume("simulation"))
            return {"emitted": event_name, **result}
        if event_name == "limit_reached":
            status = self.engine.status()
            remaining = status["remaining_today_seconds"]
            if remaining is not None and remaining > 0:
                result = await self._engine_action(
                    lambda: self.engine.grant_daily_time(-int(remaining), "simulation: limit reached")
                )
            else:
                result = await self._engine_action(self.engine.tick)
            return {"emitted": event_name, **result}
        if event_name == "game_unresponsive":
            await self._record_side_effect_event(
                "simulation.game_unresponsive", {"game": self.engine.status().get("game")}, "warning"
            )
            return {"emitted": event_name, "status": self.engine.status()}
        if event_name == "service_restart_checkpoint":
            async with self._lock:
                if self.engine.session_id:
                    self.storage.checkpoint_session(
                        self.engine.session_id, self.engine.session_duration, self.clock.now_utc()
                    )
            await self._record_side_effect_event("simulation.restart_checkpoint", {}, "warning")
            return {"emitted": event_name, "status": self.engine.status()}
        raise RpcError("invalid_params", f"unsupported simulation event: {event_name}")

    async def _consume_detector(self, queue: asyncio.Queue[DetectorEvent]) -> None:
        while True:
            event = await queue.get()
            try:
                if event.type == DetectorEventType.ERROR:
                    await self._record_side_effect_event(
                        "detector.error", {"reason": event.reason or "unknown"}, "warning"
                    )
                    continue
                if event.game and event.game.source != "decky" and self.decky_signal_is_recent():
                    current = self.engine.status().get("game")
                    if current and current.get("source") == "decky":
                        continue
                async with self._lock:
                    if event.type in {DetectorEventType.STARTED, DetectorEventType.CHANGED} and event.game:
                        events = self.engine.set_game(event.game, reason=event.reason or event.type.value)
                    elif event.type == DetectorEventType.STOPPED:
                        current = self.engine.current_game
                        if event.game and current and event.game.app_id and current.app_id != event.game.app_id:
                            events = []
                        else:
                            events = self.engine.stop_game(reason=event.reason or "detector_exit")
                    elif event.type == DetectorEventType.SUSPEND:
                        events = self.engine.suspend("detector")
                    elif event.type == DetectorEventType.RESUME:
                        events = self.engine.resume("detector")
                    else:
                        events = []
                await self._dispatch_many(events)
                self._tick_wake.set()
            except (DomainError, ValueError):
                LOGGER.exception("detector event rejected")

    async def _tick_loop(self) -> None:
        while True:
            async with self._lock:
                events = self.engine.tick()
                status = self.engine.status()
            await self._dispatch_many(events)
            timer_running = status["timer"]["state"] == TimerState.RUNNING.value
            active = status["game"] is not None or (
                timer_running and not self.config["timer"]["count_only_while_playing"]
            )
            timeout = 5.0 if active else 30.0
            self._tick_wake.clear()
            try:
                await asyncio.wait_for(self._tick_wake.wait(), timeout=timeout)
            except TimeoutError:
                pass

    async def _dispatch_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self._dispatch(event)

    async def _dispatch(self, event: DomainEvent) -> None:
        payload = event.to_dict()
        await self.event_bus.publish(payload)
        LOGGER.log(
            getattr(logging, event.severity.upper(), logging.INFO),
            event.kind,
            extra={"event": event.kind},
        )
        if event.kind == "notification.warning":
            notice = Notification(
                title=str(event.payload.get("title", "SteamOS Time Guardian")),
                body=str(event.payload.get("body", "")),
                urgency=str(event.payload.get("urgency", "normal")),
                persistent=bool(event.payload.get("persistent", False)),
            )
            await self.notifier.send(notice)
        elif event.kind == "restriction.activated":
            level = int(event.payload.get("level", 0))
            if event.payload.get("persistent_notice_required"):
                reason = str(event.payload.get("reason", "limit"))
                await self.notifier.send(
                    Notification(
                        title="Play is currently restricted",
                        body=f"Reason: {reason.replace('_', ' ')}. Restriction level {level} is active.",
                        urgency="critical",
                        persistent=True,
                    )
                )
            game = self.engine.current_game
            if game and level >= 2:
                self.enforcement.arm(
                    game,
                    self.config,
                    level,
                    str(event.payload.get("reason", "limit")),
                )
        elif event.kind in {
            "enforcement.new_game_blocked",
            "enforcement.game_started_while_restricted",
        }:
            game_payload = event.payload.get("game", {})
            if isinstance(game_payload, dict) and self.engine.current_game:
                launch_block = event.kind == "enforcement.new_game_blocked"
                self.enforcement.arm(
                    self.engine.current_game,
                    self.config,
                    max(3, self.engine.restriction_level)
                    if launch_block
                    else max(2, self.engine.restriction_level),
                    self.engine.restriction_reason.value,
                    launch_block=launch_block,
                )
        elif event.kind in {"restriction.cleared", "game.stopped"}:
            self.enforcement.cancel()

    async def _record_side_effect_event(
        self, kind: str, payload: dict[str, Any], severity: str
    ) -> None:
        now = self.clock.now_utc()
        self.storage.record_event(kind, now, payload)
        event = DomainEvent(kind=kind, occurred_at=now, payload=payload, severity=severity)
        await self.event_bus.publish(event.to_dict())
        LOGGER.log(
            getattr(logging, severity.upper(), logging.INFO),
            kind,
            extra={"event": kind},
        )

    @staticmethod
    def _require_dict(params: dict[str, Any], key: str) -> dict[str, Any]:
        value = params.get(key)
        if not isinstance(value, dict):
            raise RpcError("invalid_params", f"{key} must be an object")
        return value

    @staticmethod
    def _require_text(params: dict[str, Any], key: str, minimum: int, maximum: int) -> str:
        value = params.get(key)
        if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
            raise RpcError("invalid_params", f"{key} must contain {minimum}..{maximum} characters")
        return value.strip()

    @staticmethod
    def _require_int(
        params: dict[str, Any], key: str, minimum: int, maximum: int, *, default: int | None = None
    ) -> int:
        value = params.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise RpcError("invalid_params", f"{key} must be an integer from {minimum} to {maximum}")
        return value

    @staticmethod
    def _require_bool(
        params: dict[str, Any], key: str, *, default: bool | None = None
    ) -> bool:
        value = params.get(key, default)
        if not isinstance(value, bool):
            raise RpcError("invalid_params", f"{key} must be boolean")
        return value

    @staticmethod
    def _optional_app_id(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise RpcError("invalid_params", "app_id must be a decimal string")
        text = str(value)
        if len(text) > 32 or not text.isdigit():
            raise RpcError("invalid_params", "app_id must be a decimal string")
        return text

    @staticmethod
    def _require_pids(value: Any) -> tuple[int, ...]:
        if not isinstance(value, list) or len(value) > 256:
            raise RpcError("invalid_params", "pids must be a list with at most 256 entries")
        result: list[int] = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
                raise RpcError("invalid_params", "pids must contain positive integers")
            if item not in result:
                result.append(item)
        return tuple(result)

    @staticmethod
    def _validate_day_key(value: str) -> str:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise RpcError("invalid_params", "day must use YYYY-MM-DD") from exc


async def run_service(*, foreground: bool = True, simulation: bool | None = None) -> None:
    service = GuardianService(foreground=foreground, simulation_override=simulation)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, service.request_stop)
        except (NotImplementedError, RuntimeError):
            pass
    await service.start()
    try:
        await service.wait()
    finally:
        await service.stop()
