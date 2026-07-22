"""Authenticated newline-delimited JSON RPC over a local Unix domain socket."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
import stat
import struct
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .events import EventBus

MAX_MESSAGE_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_METHOD_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
LOGGER = logging.getLogger("stg.ipc")


class RpcError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class UnixRpcServer:
    def __init__(
        self,
        path: Path,
        handler: Callable[[str, dict[str, Any]], Awaitable[Any]],
        event_bus: EventBus,
    ):
        self.path = path
        self.handler = handler
        self.event_bus = event_bus
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            existing_mode = self.path.lstat().st_mode
        except FileNotFoundError:
            existing_mode = None
        if existing_mode is not None:
            if not stat.S_ISSOCK(existing_mode):
                raise RuntimeError(f"refusing to replace non-socket path {self.path}")
            try:
                self.path.unlink()
            except OSError as exc:
                raise RuntimeError(f"cannot remove stale socket {self.path}: {exc}") from exc
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.path),
            limit=MAX_MESSAGE_BYTES + 1,
        )
        os.chmod(self.path, 0o600)

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            self._verify_peer(writer)
            while not reader.at_eof():
                try:
                    line = await reader.readline()
                except ValueError:
                    await self._write_error(writer, None, "message_too_large", "message exceeds 64 KiB")
                    break
                if not line:
                    break
                if len(line) > MAX_MESSAGE_BYTES:
                    await self._write_error(writer, None, "message_too_large", "message exceeds 64 KiB")
                    break
                request_id: str | int | None = None
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise RpcError("invalid_request", "request must be a JSON object")
                    request_id = request.get("id")
                    if request_id is not None and not isinstance(request_id, (str, int)):
                        raise RpcError("invalid_request", "id must be a string, integer, or null")
                    method = request.get("method")
                    params = request.get("params", {})
                    if not isinstance(method, str) or not _METHOD_RE.fullmatch(method):
                        raise RpcError("invalid_method", "method name is invalid")
                    if not isinstance(params, dict):
                        raise RpcError("invalid_params", "params must be an object")
                    if method == "events.subscribe":
                        await self._write_result(writer, request_id, {"subscribed": True})
                        await self._stream_events(writer)
                        return
                    result = await self.handler(method, params)
                    await self._write_result(writer, request_id, result)
                except json.JSONDecodeError:
                    await self._write_error(writer, request_id, "invalid_json", "malformed JSON")
                except RpcError as exc:
                    await self._write_error(writer, request_id, exc.code, exc.message)
                except (ValueError, KeyError, TypeError) as exc:
                    await self._write_error(writer, request_id, "invalid_params", str(exc))
                except Exception:
                    LOGGER.exception("unhandled RPC request failure")
                    await self._write_error(writer, request_id, "internal_error", "request failed")
        except PermissionError as exc:
            LOGGER.warning("rejected Unix socket peer: %s", exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _verify_peer(self, writer: asyncio.StreamWriter) -> None:
        sock = writer.get_extra_info("socket")
        if sock is None or not hasattr(socket, "SO_PEERCRED"):
            return
        credentials = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _, uid, _ = struct.unpack("3i", credentials)
        if uid != os.getuid():
            raise PermissionError("peer UID does not match daemon UID")

    async def _stream_events(self, writer: asyncio.StreamWriter) -> None:
        async with self.event_bus.subscribe() as queue:
            while True:
                event = await queue.get()
                payload = json.dumps({"event": event}, ensure_ascii=False, separators=(",", ":"))
                writer.write(payload.encode("utf-8") + b"\n")
                await writer.drain()

    @staticmethod
    async def _write_result(writer: asyncio.StreamWriter, request_id: Any, result: Any) -> None:
        payload = json.dumps({"id": request_id, "result": result}, ensure_ascii=False, separators=(",", ":"))
        writer.write(payload.encode("utf-8") + b"\n")
        await writer.drain()

    @staticmethod
    async def _write_error(
        writer: asyncio.StreamWriter, request_id: Any, code: str, message: str
    ) -> None:
        payload = json.dumps(
            {"id": request_id, "error": {"code": code, "message": message}},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        writer.write(payload.encode("utf-8") + b"\n")
        await writer.drain()


class UnixRpcClient:
    def __init__(self, path: Path, timeout: float = 5.0):
        self.path = path
        self.timeout = timeout
        self._request_id = 0

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.path), limit=MAX_RESPONSE_BYTES + 1),
                timeout=self.timeout,
            )
        except (OSError, TimeoutError) as exc:
            raise RpcError("service_unavailable", f"cannot connect to {self.path}: {exc}") from exc
        try:
            request = {"id": self._request_id, "method": method, "params": params or {}}
            writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=self.timeout)
            if not line:
                raise RpcError("connection_closed", "service closed the connection")
            if len(line) > MAX_RESPONSE_BYTES:
                raise RpcError("response_too_large", "service response exceeds 32 MiB")
            response = json.loads(line)
            if "error" in response:
                error = response["error"]
                raise RpcError(str(error.get("code", "error")), str(error.get("message", "request failed")))
            return response.get("result")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass
