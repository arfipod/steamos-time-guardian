from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
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
        tables = {
            row[0]
            for row in self.storage.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertIn("schema_migrations", tables)
        self.assertIn("usage_buckets", tables)
        self.assertEqual(len(list(self.path.parent.glob("guardian.pre-v1-migration-*.db"))), 1)

    def test_migrates_v2_database_with_usage_buckets(self):
        self.storage.close()
        self.path.unlink()
        connection = sqlite3.connect(self.path)
        connection.executescript(MIGRATIONS[1])
        connection.executescript(MIGRATIONS[2])
        connection.execute("PRAGMA user_version=2")
        connection.close()

        self.storage = Storage(self.path)
        self.storage.open()

        self.assertEqual(self.storage.schema_version(), CURRENT_DB_SCHEMA)
        columns = {row[1] for row in self.storage.connection.execute("PRAGMA table_info(usage_buckets)")}
        self.assertEqual(
            columns,
            {"day_key", "bucket_index", "app_key", "app_id", "app_name", "seconds"},
        )
        self.assertEqual(len(list(self.path.parent.glob("guardian.pre-v2-migration-*.db"))), 1)

    def test_new_database_does_not_create_empty_migration_backup(self):
        self.assertEqual(list(self.path.parent.glob("guardian.pre-v*-migration-*.db")), [])

    def test_json_export_is_not_silently_limited_to_one_thousand_events(self):
        for index in range(1005):
            self.storage.record_event("bulk", self.now + timedelta(seconds=index), {"index": index})
        exported = json.loads(self.storage.export("json"))
        self.assertGreaterEqual(len(exported["events"]), 1005)

    def test_usage_buckets_aggregate_and_activity_summary(self):
        test_game = GameIdentity("10", "Test Game", "simulation")
        other_game = GameIdentity("20", "Other Game", "simulation")
        first = self.storage.open_session("2026-07-18", test_game, self.now - timedelta(days=2))
        self.storage.close_session(first, 120, self.now - timedelta(days=2), "normal_exit")
        second = self.storage.open_session("2026-07-18", other_game, self.now - timedelta(days=2, minutes=-1))
        self.storage.close_session(second, 30, self.now - timedelta(days=2, minutes=-1), "normal_exit")
        third = self.storage.open_session("2026-07-20", test_game, self.now)
        self.storage.close_session(third, 240, self.now, "normal_exit")

        added = self.storage.add_usage_buckets(
            [
                {
                    "day_key": "2026-07-18",
                    "bucket_index": 0,
                    "app_key": "steam:10",
                    "app_id": "10",
                    "app_name": "Test Game",
                    "seconds": 50.25,
                },
                {
                    "day_key": "2026-07-18",
                    "bucket_index": 0,
                    "app_key": "steam:10",
                    "app_id": "10",
                    "app_name": "Test Game",
                    "seconds": 9.75,
                },
                {
                    "day_key": "2026-07-18",
                    "bucket_index": 1,
                    "app_key": "steam:20",
                    "app_id": "20",
                    "app_name": "Other Game",
                    "seconds": 20,
                },
                {
                    "day_key": "2026-07-20",
                    "bucket_index": 5,
                    "app_key": "steam:10",
                    "app_id": "10",
                    "app_name": "Test Game",
                    "seconds": 120,
                },
            ]
        )

        self.assertEqual(added, 4)
        self.assertEqual(
            self.storage.list_usage_buckets(),
            [
                {
                    "day_key": "2026-07-18",
                    "bucket_index": 0,
                    "app_key": "steam:10",
                    "app_id": "10",
                    "app_name": "Test Game",
                    "seconds": 60,
                },
                {
                    "day_key": "2026-07-18",
                    "bucket_index": 1,
                    "app_key": "steam:20",
                    "app_id": "20",
                    "app_name": "Other Game",
                    "seconds": 20,
                },
                {
                    "day_key": "2026-07-20",
                    "bucket_index": 5,
                    "app_key": "steam:10",
                    "app_id": "10",
                    "app_name": "Test Game",
                    "seconds": 120,
                },
            ],
        )

        summary = self.storage.activity_summary(date(2026, 7, 20), 3, "Europe/Madrid")

        self.assertEqual(summary["total_seconds"], 390)
        self.assertEqual(
            summary["days"],
            [
                {"day_key": "2026-07-18", "total_seconds": 150},
                {"day_key": "2026-07-19", "total_seconds": 0},
                {"day_key": "2026-07-20", "total_seconds": 240},
            ],
        )
        self.assertEqual(
            summary["top_games"][0],
            {
                "app_id": "10",
                "app_name": "Test Game",
                "seconds": 360,
                "sessions": 2,
            },
        )
        self.assertEqual(summary["heatmap"]["recorded_seconds"], 200)
        self.assertEqual(summary["heatmap"]["max_seconds"], 120)
        self.assertTrue(summary["heatmap"]["available"])
        self.assertEqual(
            summary["peak"],
            {"day_key": "2026-07-20", "bucket_index": 5, "seconds": 120},
        )
        self.assertEqual(
            summary["heatmap"]["days"][0],
            {"day_key": "2026-07-18", "total_seconds": 150, "buckets": [60, 20, 0, 0, 0, 0]},
        )
        self.assertEqual(
            summary["heatmap"]["days"][1],
            {"day_key": "2026-07-19", "total_seconds": 0, "buckets": [0, 0, 0, 0, 0, 0]},
        )
        self.assertEqual(
            summary["heatmap"]["days"][2],
            {"day_key": "2026-07-20", "total_seconds": 240, "buckets": [0, 0, 0, 0, 0, 120]},
        )
        self.assertEqual(summary["recent_sessions"][0]["app_name"], "Test Game")

    def test_usage_buckets_are_exported_and_cleared_with_history(self):
        entry = {
            "day_key": "2026-07-20",
            "bucket_index": 3,
            "app_key": "steam:10",
            "app_id": "10",
            "app_name": "Test Game",
            "seconds": 60,
        }
        self.storage.add_usage_buckets([entry])

        exported = json.loads(self.storage.export("json"))
        self.assertEqual(exported["usage_buckets"], [entry])

        self.storage.clear_history()
        self.assertEqual(self.storage.list_usage_buckets(), [])

    def test_activity_summary_does_not_infer_historical_heatmap(self):
        game = GameIdentity("10", "Historical Game", "simulation")
        session = self.storage.open_session("2026-07-20", game, self.now)
        self.storage.close_session(session, 3600, self.now, "normal_exit")

        summary = self.storage.activity_summary(date(2026, 7, 20), 1, "Europe/Madrid")

        self.assertEqual(summary["total_seconds"], 3600)
        self.assertFalse(summary["heatmap"]["available"])
        self.assertEqual(summary["heatmap"]["recorded_seconds"], 0)
        self.assertIsNone(summary["peak"])
        self.assertEqual(
            summary["heatmap"]["days"],
            [{"day_key": "2026-07-20", "total_seconds": 3600, "buckets": [0] * 6}],
        )

    def test_activity_summary_groups_stable_and_name_only_games(self):
        sessions = (
            (GameIdentity("10", "Original Steam Game", "simulation"), 60),
            (GameIdentity("10", "Renamed Steam Game", "simulation"), 40),
            (GameIdentity("0", "Shortcut", "simulation"), 20),
            (GameIdentity(None, "Shortcut", "simulation"), 30),
        )
        for index, (game, seconds) in enumerate(sessions):
            when = self.now + timedelta(seconds=index)
            session = self.storage.open_session("2026-07-20", game, when)
            self.storage.close_session(session, seconds, when, "normal_exit")

        summary = self.storage.activity_summary(date(2026, 7, 20), 1, "Europe/Madrid")

        self.assertEqual(
            summary["top_games"],
            [
                {
                    "app_id": "10",
                    "app_name": "Renamed Steam Game",
                    "seconds": 100,
                    "sessions": 2,
                },
                {
                    "app_id": None,
                    "app_name": "Shortcut",
                    "seconds": 50,
                    "sessions": 2,
                },
            ],
        )

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
        self.storage.add_usage_buckets(
            [
                {
                    "day_key": "2026-01-01",
                    "bucket_index": 0,
                    "app_key": "steam:12",
                    "app_id": "12",
                    "app_name": "Old",
                    "seconds": 10,
                }
            ]
        )
        deleted = self.storage.enforce_retention(90, self.now)
        self.assertGreaterEqual(deleted["sessions"], 1)
        self.assertGreaterEqual(deleted["adjustments"], 1)
        self.assertGreaterEqual(deleted["notification_marks"], 1)
        self.assertGreaterEqual(deleted["usage_buckets"], 1)
