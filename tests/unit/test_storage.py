from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from stg.models import GameIdentity, TimerSnapshot, TimerState
from stg.storage import CURRENT_DB_SCHEMA, MIGRATIONS, DatabaseError, Storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "guardian.db"
        self.storage = Storage(self.path)
        self.storage.open()
        self.now = datetime(2026, 7, 20, 12, tzinfo=UTC)

    def tearDown(self):
        self.storage.close()
        self.temp.cleanup()

    def test_open_checkpoint_close_and_export(self):
        game = GameIdentity("10", "Test Game", "simulation", (123,), 1.0)
        session = self.storage.open_session("2026-07-20", game, self.now)
        self.storage.checkpoint_session(session, 125.5, self.now + timedelta(seconds=126))
        self.storage.close_session(session, 130, self.now + timedelta(seconds=130), "normal_exit")
        rows = self.storage.list_sessions()
        self.assertEqual(rows[0]["duration_seconds"], 130)
        self.assertEqual(rows[0]["metadata"]["pids"], [123])
        self.assertIn("Test Game", self.storage.export("csv"))
        exported = json.loads(self.storage.export("json"))
        self.assertEqual(exported["sessions"][0]["app_id"], "10")
        self.assertTrue(any(event["event_type"] == "game_started" for event in exported["events"]))

    def test_only_one_open_session(self):
        game = GameIdentity("10", "One", "simulation")
        self.storage.open_session("2026-07-20", game, self.now)
        with self.assertRaises(DatabaseError):
            self.storage.open_session("2026-07-20", game, self.now)

    def test_recover_incomplete_session(self):
        game = GameIdentity("11", "Recovery", "simulation")
        session = self.storage.open_session("2026-07-20", game, self.now)
        self.storage.checkpoint_session(session, 42, self.now + timedelta(seconds=42))
        recovered = self.storage.recover_open_session(self.now + timedelta(minutes=2))
        self.assertEqual(recovered["id"], session)
        self.assertEqual(self.storage.list_sessions()[0]["reason"], "service_restart_recovery")

    def test_timer_round_trip(self):
        timer = TimerSnapshot(TimerState.PAUSED, 600, 321.5, "close", "generation", "start", "update")
        self.storage.save_timer(timer)
        loaded = self.storage.load_timer()
        self.assertEqual(loaded.state, TimerState.PAUSED)
        self.assertEqual(loaded.remaining_seconds, 321.5)

    def test_adjustments_and_summary(self):
        self.storage.grant_adjustment("2026-07-20", 900, "bonus", self.now)
        self.assertEqual(self.storage.adjustment_for_day("2026-07-20"), 900)
        summary = self.storage.weekly_summary(self.now.date())
        self.assertEqual(len(summary["days"]), 7)

    def test_migrates_v1_database(self):
        self.storage.close()
        self.path.unlink()
        connection = sqlite3.connect(self.path)
        connection.executescript(MIGRATIONS[1])
        connection.execute("PRAGMA user_version=1")
        connection.close()
        self.storage = Storage(self.path)
        self.storage.open()
        self.assertEqual(self.storage.schema_version(), CURRENT_DB_SCHEMA)
        tables = {row[0] for row in self.storage.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("schema_migrations", tables)
        self.assertEqual(len(list(self.path.parent.glob("guardian.pre-v1-migration-*.db"))), 1)

    def test_new_database_does_not_create_empty_migration_backup(self):
        self.assertEqual(list(self.path.parent.glob("guardian.pre-v*-migration-*.db")), [])

    def test_json_export_is_not_silently_limited_to_one_thousand_events(self):
        for index in range(1005):
            self.storage.record_event("bulk", self.now + timedelta(seconds=index), {"index": index})
        exported = json.loads(self.storage.export("json"))
        self.assertGreaterEqual(len(exported["events"]), 1005)

    def test_retention_keeps_recent_and_deletes_old(self):
        game = GameIdentity("12", "Old", "simulation")
        session = self.storage.open_session("2026-01-01", game, self.now - timedelta(days=100))
        self.storage.close_session(session, 10, self.now - timedelta(days=100), "exit")
        self.storage.grant_adjustment(
            "2026-01-01", 60, "old adjustment", self.now - timedelta(days=100)
        )
        self.storage.mark_notification(
            "daily", "2026-01-01", 300, self.now - timedelta(days=100)
        )
        deleted = self.storage.enforce_retention(90, self.now)
        self.assertGreaterEqual(deleted["sessions"], 1)
        self.assertGreaterEqual(deleted["adjustments"], 1)
        self.assertGreaterEqual(deleted["notification_marks"], 1)
