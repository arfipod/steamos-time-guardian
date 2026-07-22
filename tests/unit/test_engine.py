from __future__ import annotations

import unittest
from datetime import UTC, datetime

from stg.engine import DomainError
from stg.models import GameIdentity, TimerState

from tests.helpers import EngineFixture, test_config


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = EngineFixture()
        self.engine = self.fixture.engine
        self.clock = self.fixture.clock

    def tearDown(self):
        self.fixture.close()

    def start_game(self, app_id="100", name="Game"):
        return self.engine.set_game(GameIdentity(app_id, name, "simulation", (999,), 1.0))

    def test_counts_only_while_game_is_active(self):
        self.clock.advance(30)
        self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 0)
        self.start_game()
        self.clock.advance(125)
        self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 125)
        self.engine.stop_game()
        self.clock.advance(20)
        self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 125)

    def test_timer_pause_resume_and_adjust(self):
        self.start_game()
        self.engine.start_timer(600)
        self.clock.advance(60)
        self.engine.tick()
        self.assertEqual(self.engine.status()["timer"]["remaining_seconds"], 540)
        self.engine.pause_timer()
        self.clock.advance(30)
        self.engine.tick()
        self.assertEqual(self.engine.status()["timer"]["remaining_seconds"], 540)
        self.engine.adjust_timer(60)
        self.engine.resume_timer()
        self.clock.advance(10)
        self.engine.tick()
        self.assertEqual(self.engine.status()["timer"]["remaining_seconds"], 590)

    def test_timer_does_not_count_idle_by_default(self):
        self.engine.start_timer(600)
        self.clock.advance(60)
        self.engine.tick()
        self.assertEqual(self.engine.status()["timer"]["remaining_seconds"], 600)

    def test_suspend_gap_not_counted(self):
        self.start_game()
        self.clock.advance(10)
        self.engine.tick()
        self.clock.advance(0, wall_seconds=3600)
        events = self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 10)
        self.assertIn("system.suspend_inferred", [event.kind for event in events])

    def test_activity_buckets_split_at_a_four_hour_boundary(self):
        self.fixture.close()
        self.fixture = EngineFixture(datetime(2026, 7, 20, 3, 59, 50, tzinfo=UTC))
        self.engine, self.clock = self.fixture.engine, self.fixture.clock
        self.start_game()

        self.clock.advance(20)
        self.engine.tick()
        self.engine.stop_game()

        buckets = self.fixture.storage.list_usage_buckets()
        by_index = {bucket["bucket_index"]: bucket["seconds"] for bucket in buckets}
        self.assertEqual(by_index, {0: 10, 1: 10})

    def test_activity_buckets_omit_a_suspend_gap(self):
        self.start_game()
        self.clock.advance(10)
        self.engine.tick()
        self.clock.advance(0, wall_seconds=3600)
        self.engine.tick()

        buckets = self.fixture.storage.list_usage_buckets()
        self.assertEqual(sum(bucket["seconds"] for bucket in buckets), 10)

    def test_activity_buckets_rotate_with_the_accounting_day(self):
        self.fixture.close()
        config = test_config(daily_limits={**test_config()["daily_limits"], "reset_at": "00:00", "timezone": "UTC"})
        self.fixture = EngineFixture(datetime(2026, 7, 20, 23, 59, 50, tzinfo=UTC), config)
        self.engine, self.clock = self.fixture.engine, self.fixture.clock
        self.start_game()

        self.clock.advance(20)
        self.engine.tick()

        buckets = self.fixture.storage.list_usage_buckets()
        by_day_and_index = {
            (bucket["day_key"], bucket["bucket_index"]): bucket["seconds"] for bucket in buckets
        }
        self.assertEqual(
            by_day_and_index,
            {("2026-07-20", 5): 10, ("2026-07-21", 0): 10},
        )

    def test_activity_buckets_preserve_elapsed_time_through_dst_fallback(self):
        self.fixture.close()
        config = test_config(
            daily_limits={
                **test_config()["daily_limits"],
                "reset_at": "00:00",
                "timezone": "Europe/Madrid",
            }
        )
        self.fixture = EngineFixture(datetime(2026, 10, 25, 0, 30, tzinfo=UTC), config)
        self.engine, self.clock = self.fixture.engine, self.fixture.clock
        self.start_game()

        self.clock.advance(3 * 60 * 60)
        self.engine.tick()

        buckets = self.fixture.storage.list_usage_buckets()
        by_index = {bucket["bucket_index"]: bucket["seconds"] for bucket in buckets}
        self.assertEqual(by_index, {0: 9000, 1: 1800})
        self.assertEqual(sum(by_index.values()), 3 * 60 * 60)

    def test_explicit_suspend_resume(self):
        self.start_game()
        self.engine.suspend("test")
        self.clock.advance(100)
        self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 0)
        self.engine.resume("test")
        self.clock.advance(10)
        self.engine.tick()
        self.assertEqual(self.engine.status()["played_today_seconds"], 10)

    def test_daily_reset_rotates_active_session(self):
        self.fixture.close()
        config = test_config(daily_limits={**test_config()["daily_limits"], "reset_at": "00:00", "timezone": "UTC"})
        self.fixture = EngineFixture(datetime(2026, 7, 20, 23, 59, 50, tzinfo=UTC), config)
        self.engine, self.clock = self.fixture.engine, self.fixture.clock
        self.start_game()
        self.clock.advance(20)
        events = self.engine.tick()
        self.assertEqual(self.engine.day_key, "2026-07-21")
        self.assertIn("daily.reset", [event.kind for event in events])
        sessions = self.fixture.storage.list_sessions()
        self.assertEqual(len(sessions), 2)
        old_session = next(item for item in sessions if item["day_key"] == "2026-07-20")
        self.assertEqual(old_session["duration_seconds"], 10)
        self.assertEqual(self.engine.status()["played_today_seconds"], 10)
        self.assertEqual(round(self.engine.session_duration), 10)

    def test_game_change_closes_previous_session(self):
        self.start_game("100", "First")
        self.clock.advance(15)
        self.engine.set_game(GameIdentity("200", "Second", "simulation"))
        sessions = self.fixture.storage.list_sessions()
        old = next(item for item in sessions if item["app_id"] == "100")
        self.assertEqual(old["reason"], "game_changed")
        self.assertEqual(self.engine.status()["game"]["app_id"], "200")

    def test_warning_is_not_repeated(self):
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 31
        self.start_game()
        self.clock.advance(61)
        first = self.engine.tick()
        second = self.engine.tick()
        self.assertEqual(sum(event.kind == "notification.warning" for event in first), 1)
        self.assertEqual(sum(event.kind == "notification.warning" for event in second), 0)

    def test_daily_limit_activates_configured_restriction(self):
        self.engine.config["restriction"]["level"] = 2
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 1
        self.start_game()
        self.clock.advance(61)
        events = self.engine.tick()
        self.assertEqual(self.engine.status()["restriction"]["effective_level"], 2)
        self.assertIn("restriction.activated", [event.kind for event in events])
        with self.assertRaises(DomainError):
            self.engine.start_timer(300)


    def test_tracking_only_records_exhaustion_without_restricting(self):
        self.engine.config["restriction"]["level"] = 0
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 1
        self.start_game()
        self.clock.advance(61)
        events = self.engine.tick()
        self.assertEqual(self.engine.status()["restriction"]["effective_level"], 0)
        self.assertIn("allowance.exhausted", [event.kind for event in events])
        self.assertNotIn("restriction.cleared", [event.kind for event in events])

    def test_level_two_reapplies_when_game_starts_while_already_restricted(self):
        self.engine.config["restriction"]["level"] = 2
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 0
        events = self.start_game()
        self.assertIn(
            "enforcement.game_started_while_restricted",
            [event.kind for event in events],
        )

    def test_bonus_clears_daily_restriction(self):
        self.engine.config["restriction"]["level"] = 1
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 1
        self.start_game()
        self.clock.advance(61)
        self.engine.tick()
        self.engine.grant_daily_time(600, "exception")
        self.assertEqual(self.engine.status()["restriction"]["effective_level"], 0)


    def test_next_warning_prefers_the_nearest_active_allowance(self):
        for day in self.engine.config["daily_limits"]["weekly"].values():
            day["minutes"] = 60
        self.start_game()
        self.engine.start_timer(600)
        warning = self.engine.status()["next_warning"]
        self.assertEqual(warning["scope"], "timer")
        self.assertEqual(warning["threshold_seconds"], 300)
        self.assertEqual(warning["play_seconds_until"], 300)

    def test_disabled_daily_limits_do_not_enforce_allowed_periods(self):
        self.engine.config["daily_limits"]["enabled"] = False
        self.engine.config["daily_limits"]["allowed_periods"] = [
            {"start": "18:00", "end": "19:00", "days": ["monday"]}
        ]
        events = self.engine.tick()
        status = self.engine.status()
        self.assertTrue(status["within_allowed_period"])
        self.assertEqual(status["restriction"]["reason"], "none")
        self.assertNotIn("restriction.activated", [event.kind for event in events])

    def test_timer_expiration_override(self):
        self.engine.config["restriction"]["level"] = 0
        self.start_game()
        self.engine.start_timer(60, "close")
        self.clock.advance(60)
        self.engine.tick()
        self.assertEqual(self.engine.timer.state, TimerState.EXPIRED)
        self.assertEqual(self.engine.status()["restriction"]["effective_level"], 2)
