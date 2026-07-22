from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from stg.schedule import accounting_day, accounting_day_key, limit_for_day, parse_hhmm, seconds_until_reset, within_allowed_period
from tests.helpers import test_config


class ScheduleTests(unittest.TestCase):
    def test_accounting_day_before_custom_reset(self):
        now = datetime(2026, 7, 21, 2, 30, tzinfo=UTC)
        self.assertEqual(accounting_day(now, "04:00", "UTC"), date(2026, 7, 20))
        self.assertEqual(accounting_day_key(now, "04:00", "UTC"), "2026-07-20")

    def test_accounting_day_at_reset(self):
        now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
        self.assertEqual(accounting_day(now, "04:00", "UTC"), date(2026, 7, 21))

    def test_seconds_until_reset(self):
        now = datetime(2026, 7, 21, 23, 59, 30, tzinfo=UTC)
        self.assertEqual(seconds_until_reset(now, "00:00", "UTC"), 30)

    def test_weekday_limit_and_unlimited(self):
        config = test_config()
        config["daily_limits"]["weekly"]["monday"] = {"minutes": 90, "unlimited": False}
        config["daily_limits"]["weekly"]["tuesday"] = {"minutes": 0, "unlimited": True}
        self.assertEqual(limit_for_day(config, date(2026, 7, 20)), 5400)
        self.assertIsNone(limit_for_day(config, date(2026, 7, 21)))

    def test_allowed_period_normal_and_overnight(self):
        config = test_config()
        config["daily_limits"]["allowed_periods"] = [
            {"start": "16:00", "end": "18:00", "days": ["monday"]},
            {"start": "22:00", "end": "02:00", "days": ["monday"]},
        ]
        self.assertTrue(within_allowed_period(config, datetime(2026, 7, 20, 17, tzinfo=UTC)))
        self.assertTrue(within_allowed_period(config, datetime(2026, 7, 20, 23, tzinfo=UTC)))
        self.assertTrue(within_allowed_period(config, datetime(2026, 7, 21, 1, tzinfo=UTC)))
        self.assertFalse(within_allowed_period(config, datetime(2026, 7, 20, 12, tzinfo=UTC)))

    def test_seconds_until_reset_handles_daylight_saving_days(self):
        spring = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
        autumn = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
        self.assertEqual(seconds_until_reset(spring, "00:00", "Europe/Madrid"), 23 * 3600)
        self.assertEqual(seconds_until_reset(autumn, "00:00", "Europe/Madrid"), 25 * 3600)

    def test_parse_hhmm_rejects_invalid(self):
        for value in ("24:00", "12:60", "noon", "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_hhmm(value)
