from __future__ import annotations

import unittest

from stg.engine import GuardianEngine
from stg.models import GameIdentity, TimerState

from tests.helpers import EngineFixture, test_config


def warnings(events):
    return [event for event in events if event.kind == "notification.warning"]


class WarningTransitionTests(unittest.TestCase):
    def setUp(self):
        base = test_config()
        config = test_config(
            daily_limits={**base["daily_limits"], "enabled": False},
            timer={**base["timer"], "count_only_while_playing": False},
        )
        self.fixture = EngineFixture(config=config)
        self.engine = self.fixture.engine
        self.clock = self.fixture.clock

    def tearDown(self):
        self.fixture.close()

    def test_timer_does_not_emit_a_threshold_above_its_initial_duration(self):
        self.engine.start_timer(20 * 60)

        self.clock.advance(5)
        self.assertEqual(warnings(self.engine.tick()), [])
        self.assertEqual(
            self.fixture.storage.notification_thresholds("timer", self.engine.timer.generation), set()
        )

    def test_timer_emits_each_threshold_only_when_crossed(self):
        self.engine.start_timer(20 * 60)
        sequence = [(301, 15 * 60), (600, 5 * 60), (240, 60), (59, 0)]

        observed = []
        for elapsed, expected_threshold in sequence:
            self.clock.advance(elapsed)
            emitted = warnings(self.engine.tick())
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0].payload["threshold_seconds"], expected_threshold)
            observed.append(emitted[0].payload["threshold_seconds"])
            self.assertEqual(warnings(self.engine.tick()), [])

        self.assertEqual(observed, [15 * 60, 5 * 60, 60, 0])

    def test_large_elapsed_jump_emits_only_the_closest_crossed_threshold(self):
        self.engine.start_timer(20 * 60)
        generation = self.engine.timer.generation

        self.clock.advance(1000)
        emitted = warnings(self.engine.tick())

        self.assertEqual([event.payload["threshold_seconds"] for event in emitted], [5 * 60])
        self.assertEqual(
            self.fixture.storage.notification_thresholds("timer", generation),
            {15 * 60, 5 * 60},
        )
        self.assertEqual(warnings(self.engine.tick()), [])

    def test_adding_time_rearms_only_thresholds_crossed_again_later(self):
        self.engine.start_timer(20 * 60)
        self.clock.advance(301)
        self.assertEqual(warnings(self.engine.tick())[0].payload["threshold_seconds"], 15 * 60)

        self.assertEqual(warnings(self.engine.adjust_timer(5 * 60)), [])
        self.clock.advance(300)
        emitted = warnings(self.engine.tick())

        self.assertEqual([event.payload["threshold_seconds"] for event in emitted], [15 * 60])
        self.assertNotEqual(emitted[0].payload["threshold_seconds"], 30 * 60)

    def test_reviving_an_expired_timer_with_thirty_minutes_does_not_emit_thirty(self):
        self.engine.start_timer(60)
        self.clock.advance(60)
        self.assertEqual(warnings(self.engine.tick())[0].payload["threshold_seconds"], 0)

        self.assertEqual(warnings(self.engine.adjust_timer(30 * 60)), [])
        self.assertEqual(self.engine.timer.state, TimerState.PAUSED)
        self.engine.resume_timer()
        self.clock.advance(5)

        self.assertEqual(warnings(self.engine.tick()), [])

    def test_negative_adjustment_emits_exhaustion_immediately(self):
        self.engine.start_timer(20 * 60)

        emitted = warnings(self.engine.adjust_timer(-20 * 60))

        self.assertEqual(self.engine.timer.state, TimerState.EXPIRED)
        self.assertEqual([event.payload["threshold_seconds"] for event in emitted], [0])

    def test_daily_and_timer_titles_identify_their_scope(self):
        self.fixture.close()
        base = test_config()
        weekly = {
            day: {**entry, "minutes": 31, "unlimited": False}
            for day, entry in base["daily_limits"]["weekly"].items()
        }
        config = test_config(
            language="es",
            daily_limits={**base["daily_limits"], "weekly": weekly},
        )
        self.fixture = EngineFixture(config=config)
        self.engine = self.fixture.engine
        self.clock = self.fixture.clock
        self.engine.set_game(GameIdentity("100", "Game", "simulation"))
        self.engine.start_timer(20 * 60)

        self.clock.advance(61)
        daily = warnings(self.engine.tick())
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0].payload["scope"], "daily")
        self.assertTrue(daily[0].payload["title"].startswith("Límite diario:"))

        self.clock.advance(240)
        timer = warnings(self.engine.tick())
        self.assertEqual(len(timer), 1)
        self.assertEqual(timer[0].payload["scope"], "timer")
        self.assertTrue(timer[0].payload["title"].startswith("Temporizador:"))

    def test_restart_does_not_emit_stale_thresholds(self):
        self.engine.start_timer(20 * 60)
        self.clock.advance(400)
        self.engine.tick()

        restarted = GuardianEngine(self.fixture.storage, self.fixture.config, self.clock)
        self.assertEqual(restarted.timer.state, TimerState.PAUSED)
        self.assertEqual(warnings(restarted.tick()), [])


if __name__ == "__main__":
    unittest.main()
