from __future__ import annotations

import asyncio
import unittest

from stg.enforcement import (
    EnforcementManager,
    RecordingProcessController,
    SafeProcessController,
    build_plan,
)
from stg.models import GameIdentity
from tests.helpers import test_config


class EnforcementPolicyTests(unittest.TestCase):
    def test_level_zero_has_no_close_action(self):
        plan = build_plan(test_config(), 0)
        self.assertFalse(plan.request_steam_close)
        self.assertFalse(plan.allow_force_kill)

    def test_force_kill_requires_explicit_configuration(self):
        config = test_config()
        self.assertFalse(build_plan(config, 2).allow_force_kill)
        config["restriction"]["force_kill_enabled"] = True
        self.assertTrue(build_plan(config, 2).allow_force_kill)


class EnforcementManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_when_status_no_longer_restricted(self):
        controller = RecordingProcessController()
        status = {"game": {"app_id": "1", "name": "Game"}, "restriction": {"effective_level": 0}}
        events = []

        async def record(kind, payload, severity):
            events.append({"kind": kind, "payload": payload, "severity": severity})

        manager = EnforcementManager(controller, lambda: status, record, lambda: False)
        config = test_config()
        config["restriction"].update({"grace_seconds": 0, "close_timeout_seconds": 0})
        manager.arm(GameIdentity("1", "Game", "simulation"), config, 2, "test")
        await asyncio.sleep(0.05)
        self.assertEqual(controller.calls, [])
        self.assertEqual(events, [])

    async def test_records_close_and_term_attempt(self):
        controller = RecordingProcessController()
        status = {"game": {"app_id": "1", "name": "Game"}, "restriction": {"effective_level": 2}}
        events = []

        async def record(kind, payload, severity):
            events.append({"kind": kind, "payload": payload, "severity": severity})

        manager = EnforcementManager(controller, lambda: status, record, lambda: True)
        config = test_config()
        config["restriction"].update({"grace_seconds": 0, "close_timeout_seconds": 0})
        manager.arm(GameIdentity("1", "Game", "simulation", (77,)), config, 2, "limit")
        await asyncio.sleep(0.05)
        close_events = [item for item in events if item.get("kind") == "enforcement.close_requested"]
        self.assertEqual(len(close_events), 1)
        self.assertEqual(len(controller.calls), 1)
        manager.cancel()


class SafeProcessControllerTests(unittest.TestCase):
    def test_refuses_pid_fallback_without_robust_app_id(self):
        controller = SafeProcessController()
        self.assertEqual(
            controller._verified_pids(GameIdentity(None, "Non-Steam", "decky", (999999,))),
            [],
        )
        self.assertEqual(
            controller._verified_pids(GameIdentity("0", "Non-Steam", "decky", (999999,))),
            [],
        )
