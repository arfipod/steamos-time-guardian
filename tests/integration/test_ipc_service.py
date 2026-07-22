from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from stg.events import EventBus
from stg.ipc import MAX_MESSAGE_BYTES, RpcError, UnixRpcClient, UnixRpcServer
from stg.models import GameIdentity
from stg.service import GuardianService

from tests.helpers import temporary_paths


class ServiceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.paths = temporary_paths(Path(self.temp.name))
        self.service = GuardianService(paths=self.paths, simulation_override=True)
        await self.service.start()
        self.client = UnixRpcClient(self.paths.socket_file)
        await self.client.call("config.update", {"patch": {"warnings": {"native_desktop_notifications": False}}})

    async def asyncTearDown(self):
        await self.service.stop()
        self.temp.cleanup()

    async def test_status_timer_history_and_diagnostics(self):
        pong = await self.client.call("service.ping")
        self.assertTrue(pong["ok"])
        await self.client.call(
            "detector.report_foreground",
            {"running": True, "app_id": "777", "name": "IPC Game", "pids": []},
        )
        timer = await self.client.call("timer.start", {"seconds": 120, "action": "inherit"})
        self.assertEqual(timer["status"]["timer"]["state"], "running")
        status = await self.client.call("status.get")
        self.assertEqual(status["game"]["app_id"], "777")
        await self.client.call("detector.report_foreground", {"running": False})
        history = await self.client.call("history.list", {"limit": 10})
        self.assertEqual(history["sessions"][0]["app_name"], "IPC Game")
        diagnostics = await self.client.call("diagnostics.get")
        self.assertEqual(diagnostics["database"]["quick_check"], "ok")

    async def test_simulator_and_export(self):
        await self.client.call("simulation.emit", {"event": "game_started", "app_id": "888", "name": "Sim"})
        await self.client.call("simulation.emit", {"event": "game_stopped"})
        exported = await self.client.call("history.export", {"format": "json"})
        data = json.loads(exported["content"])
        self.assertEqual(data["sessions"][0]["app_id"], "888")

    async def test_concurrent_requests_are_serialized(self):
        results = await asyncio.gather(*[self.client.call("daily.grant", {"seconds": 60, "reason": f"test-{index}"}) for index in range(10)])
        self.assertEqual(len(results), 10)
        status = await self.client.call("status.get")
        self.assertEqual(status["daily_adjustment_seconds"], 600)

    async def test_invalid_and_unknown_methods_fail_cleanly(self):
        with self.assertRaises(RpcError) as unknown:
            await self.client.call("unknown.method")
        self.assertEqual(unknown.exception.code, "method_not_found")
        with self.assertRaises(RpcError):
            await self.client.call("timer.start", {"seconds": 1})

    async def test_event_subscription(self):
        reader, writer = await asyncio.open_unix_connection(str(self.paths.socket_file))
        writer.write(b'{"id":1,"method":"events.subscribe","params":{}}\n')
        await writer.drain()
        ack = json.loads(await reader.readline())
        self.assertTrue(ack["result"]["subscribed"])
        await self.client.call("daily.grant", {"seconds": 60, "reason": "subscription test"})
        message = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
        self.assertIn("event", message)
        writer.close()
        await writer.wait_closed()

    async def test_history_clear_requires_confirmation(self):
        with self.assertRaises(RpcError) as context:
            await self.client.call("history.clear", {})
        self.assertEqual(context.exception.code, "confirmation_required")

    async def test_timer_uses_configured_default_action(self):
        await self.client.call("config.update", {"patch": {"timer": {"default_action": "close"}}})
        result = await self.client.call("timer.start", {"seconds": 120})
        self.assertEqual(result["status"]["timer"]["action"], "close")

    async def test_activity_summary_is_bounded_and_local(self):
        end_day = date.fromisoformat(self.service.engine.day_key)
        game = GameIdentity("777", "IPC Game", "simulation")
        started = datetime.combine(end_day, datetime.min.time(), tzinfo=UTC)
        session_id = self.service.storage.open_session(end_day.isoformat(), game, started)
        self.service.storage.close_session(session_id, 120, started, "test")
        self.service.storage.add_usage_buckets(
            [
                {
                    "day_key": end_day.isoformat(),
                    "bucket_index": 3,
                    "app_key": "app:777",
                    "app_id": "777",
                    "app_name": "IPC Game",
                    "seconds": 120,
                }
            ]
        )

        result = await self.client.call("summary.activity", {"days": 7})

        self.assertEqual(result["range"]["end_day"], end_day.isoformat())
        self.assertEqual(len(result["days"]), 7)
        self.assertEqual(result["top_games"][0]["app_name"], "IPC Game")
        self.assertEqual(result["heatmap"]["days"][-1]["buckets"][3], 120)
        self.assertLess(len(json.dumps(result)), 64 * 1024)
        with self.assertRaises(RpcError) as invalid_days:
            await self.client.call("summary.activity", {"days": 91})
        self.assertEqual(invalid_days.exception.code, "invalid_params")

    async def test_strict_boolean_and_pid_validation(self):
        with self.assertRaises(RpcError) as boolean_error:
            await self.client.call(
                "detector.report_foreground",
                {"running": "false", "app_id": "777", "name": "Bad"},
            )
        self.assertEqual(boolean_error.exception.code, "invalid_params")
        with self.assertRaises(RpcError) as pid_error:
            await self.client.call(
                "detector.report_foreground",
                {"running": True, "app_id": "777", "name": "Bad", "pids": [True]},
            )
        self.assertEqual(pid_error.exception.code, "invalid_params")

    async def test_history_clear_refuses_an_active_session_and_then_succeeds(self):
        await self.client.call(
            "detector.report_foreground",
            {"running": True, "app_id": "777", "name": "Active", "pids": []},
        )
        with self.assertRaises(RpcError) as active_error:
            await self.client.call("history.clear", {"confirmation": "PURGE_HISTORY"})
        self.assertEqual(active_error.exception.code, "invalid_state")
        await self.client.call("detector.report_foreground", {"running": False})
        result = await self.client.call("history.clear", {"confirmation": "PURGE_HISTORY"})
        self.assertTrue(result["cleared"])
        history = await self.client.call("history.list", {"limit": 10})
        self.assertEqual(history["sessions"], [])

    async def test_oversized_request_is_rejected(self):
        reader, writer = await asyncio.open_unix_connection(str(self.paths.socket_file))
        writer.write(b"{" + b"x" * MAX_MESSAGE_BYTES + b"\n")
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
        self.assertEqual(response["error"]["code"], "message_too_large")
        writer.close()
        await writer.wait_closed()

    async def test_server_refuses_to_replace_a_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "control.sock"
            socket_path.write_text("do not replace", encoding="utf-8")

            async def handler(method, params):
                return {"method": method, "params": params}

            server = UnixRpcServer(socket_path, handler, EventBus())
            with self.assertRaisesRegex(RuntimeError, "refusing to replace non-socket"):
                await server.start()
            self.assertEqual(socket_path.read_text(encoding="utf-8"), "do not replace")

    async def test_simulation_rpc_is_rejected_outside_simulation_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = temporary_paths(Path(directory))
            service = GuardianService(paths=paths, simulation_override=False)
            await service.start()
            try:
                client = UnixRpcClient(paths.socket_file)
                with self.assertRaises(RpcError) as context:
                    await client.call("simulation.emit", {"event": "game_started"})
                self.assertEqual(context.exception.code, "simulation_disabled")
            finally:
                await service.stop()
