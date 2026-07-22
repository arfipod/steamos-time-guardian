from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from stg.clock import FakeClock
from stg.engine import GuardianEngine
from stg.models import GameIdentity
from stg.storage import Storage
from tests.helpers import test_config


class RestartRecoveryTests(unittest.TestCase):
    def test_open_session_is_closed_at_last_checkpoint_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guardian.db"
            storage = Storage(path)
            storage.open()
            clock = FakeClock(datetime(2026, 7, 20, 12, tzinfo=UTC))
            engine = GuardianEngine(storage, test_config(), clock)
            engine.set_game(GameIdentity("123", "Restart Game", "simulation"))
            clock.advance(35)
            engine.tick()
            storage.close()  # abrupt process exit: no engine.shutdown()

            restarted_storage = Storage(path)
            restarted_storage.open()
            restarted = GuardianEngine(restarted_storage, test_config(), clock)
            events = restarted.take_initial_events()
            sessions = restarted_storage.list_sessions()
            self.assertEqual(sessions[0]["reason"], "service_restart_recovery")
            self.assertGreaterEqual(sessions[0]["duration_seconds"], 35)
            self.assertIn("session.recovered", [event.kind for event in events])
            restarted_storage.close()
