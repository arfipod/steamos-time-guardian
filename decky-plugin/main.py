"""Rootless Decky backend that proxies the frontend to the user daemon's Unix socket."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import pwd
from pathlib import Path
from typing import Any

import decky

MAX_MESSAGE = 64 * 1024


def _deck_uid() -> int:
    username = getattr(decky, "DECKY_USER", None) or os.environ.get("DECKY_USER") or os.environ.get("USER")
    if username:
        try:
            return pwd.getpwnam(username).pw_uid
        except KeyError:
            pass
    return os.getuid()


def _socket_path() -> Path:
    override = os.environ.get("STG_SOCKET")
    if override:
        return Path(override)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and Path(runtime).name == str(_deck_uid()):
        return Path(runtime) / "steamos-time-guardian/control.sock"
    return Path(f"/run/user/{_deck_uid()}/steamos-time-guardian/control.sock")


class RpcFailure(RuntimeError):
    pass


class Plugin:
    def __init__(self) -> None:
        self._request_id = 0
        self._bridge_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(_socket_path())), timeout=3
            )
        except (OSError, TimeoutError) as exc:
            raise RpcFailure(f"Time Guardian daemon unavailable: {exc}") from exc
        try:
            request = {"id": self._request_id, "method": method, "params": params or {}}
            writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not line or len(line) > MAX_MESSAGE:
                raise RpcFailure("invalid response from Time Guardian daemon")
            response = json.loads(line)
            if "error" in response:
                error = response["error"]
                raise RpcFailure(str(error.get("message", "request failed")))
            return response.get("result")
        finally:
            writer.close()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                await writer.wait_closed()

    async def get_status(self) -> dict[str, Any]:
        return await self._rpc("status.get")

    async def get_config(self) -> dict[str, Any]:
        return await self._rpc("config.get")

    async def update_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict):
            raise RpcFailure("configuration patch must be an object")
        return await self._rpc("config.update", {"patch": patch})

    async def timer_start(self, minutes: int, action: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"seconds": int(minutes) * 60}
        if action is not None:
            params["action"] = action
        return await self._rpc("timer.start", params)

    async def timer_pause(self) -> dict[str, Any]:
        return await self._rpc("timer.pause")

    async def timer_resume(self) -> dict[str, Any]:
        return await self._rpc("timer.resume")

    async def timer_cancel(self) -> dict[str, Any]:
        return await self._rpc("timer.cancel")

    async def timer_adjust(self, seconds: int) -> dict[str, Any]:
        return await self._rpc("timer.adjust", {"seconds": int(seconds)})

    async def daily_grant(self, minutes: int, reason: str) -> dict[str, Any]:
        return await self._rpc("daily.grant", {"seconds": int(minutes) * 60, "reason": str(reason)})

    async def activity_summary(self, days: int = 7) -> dict[str, Any]:
        return await self._rpc("summary.activity", {"days": int(days)})

    async def history_clear(self, confirmation: str) -> dict[str, Any]:
        return await self._rpc("history.clear", {"confirmation": confirmation})

    async def weekly_summary(self) -> dict[str, Any]:
        return await self._rpc("summary.weekly")

    async def get_diagnostics(self) -> dict[str, Any]:
        return await self._rpc("diagnostics.get")

    async def heartbeat(self) -> dict[str, Any]:
        return await self._rpc("plugin.heartbeat")

    async def report_foreground(self, running: bool, app_id: str | None, name: str) -> dict[str, Any]:
        return await self._rpc(
            "detector.report_foreground",
            {"running": bool(running), "app_id": app_id, "name": str(name)},
        )

    async def report_lifetime(self, app_id: int, instance_id: int, running: bool) -> dict[str, Any]:
        return await self._rpc(
            "detector.report_lifetime",
            {"app_id": app_id, "instance_id": instance_id, "running": running},
        )

    async def report_enforcement(self, app_id: str | None, success: bool, detail: str) -> dict[str, Any]:
        return await self._rpc(
            "enforcement.report_result",
            {"app_id": app_id, "success": success, "detail": str(detail)[:300]},
        )

    async def _main(self) -> None:
        self._bridge_task = asyncio.create_task(self._event_bridge())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        decky.logger.info("SteamOS Time Guardian Decky bridge started (rootless)")

    async def _unload(self) -> None:
        for task in (self._bridge_task, self._heartbeat_task):
            if task:
                task.cancel()
        for task in (self._bridge_task, self._heartbeat_task):
            if task:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        decky.logger.info("SteamOS Time Guardian Decky bridge stopped")

    async def _uninstall(self) -> None:
        # The daemon, configuration, and history are deliberately not removed with the optional UI.
        decky.logger.info("Decky UI removed; Time Guardian daemon data retained")

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await self.heartbeat()
            except Exception as exc:
                decky.logger.debug("Time Guardian heartbeat failed: %s", exc)
            await asyncio.sleep(10)

    async def _event_bridge(self) -> None:
        delay = 1
        while True:
            writer: asyncio.StreamWriter | None = None
            try:
                reader, writer = await asyncio.open_unix_connection(str(_socket_path()))
                self._request_id += 1
                request = {"id": self._request_id, "method": "events.subscribe", "params": {}}
                writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
                await writer.drain()
                acknowledgement = await reader.readline()
                if not acknowledgement:
                    raise RpcFailure("event stream closed before acknowledgement")
                delay = 1
                while True:
                    line = await reader.readline()
                    if not line:
                        raise RpcFailure("event stream closed")
                    if len(line) > MAX_MESSAGE:
                        continue
                    payload = json.loads(line)
                    event = payload.get("event")
                    if isinstance(event, dict):
                        await decky.emit("guardian_event", event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                decky.logger.debug("Time Guardian event bridge reconnecting: %s", exc)
                await asyncio.sleep(delay)
                delay = min(30, delay * 2)
            finally:
                if writer:
                    writer.close()
                    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                        await writer.wait_closed()
