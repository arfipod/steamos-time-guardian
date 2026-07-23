from __future__ import annotations

import unittest
from pathlib import Path

from stg.cli import build_parser
from stg.i18n import display_restriction_reason, display_timer_state, format_duration, tr
from stg.models import GameIdentity
from stg.tui import TuiApplication

from tests.helpers import EngineFixture, test_config


class LocalizationTests(unittest.TestCase):
    def test_spanish_translation_and_duration(self):
        self.assertEqual(tr("es", "played_today"), "Jugado hoy")
        self.assertEqual(format_duration(65, "es"), "1min 05s")
        self.assertEqual(display_timer_state("paused", "es"), "en pausa")
        self.assertEqual(display_restriction_reason("daily_limit", "es"), "límite diario")

    def test_engine_emits_spanish_warning_payload(self):
        config = test_config(
            language="es",
            daily_limits={
                **test_config()["daily_limits"],
                "weekly": {
                    day: {"minutes": 1, "unlimited": False} for day in test_config()["daily_limits"]["weekly"]
                },
            },
            warnings={**test_config()["warnings"], "threshold_minutes": [1]},
        )
        fixture = EngineFixture(config=config)
        try:
            fixture.engine.set_game(GameIdentity("100", "Juego", "simulation"))
            fixture.clock.advance(1)
            events = fixture.engine.tick()
            payload = next(event.payload for event in events if event.kind == "notification.warning")
            self.assertEqual(payload["title"], "Límite diario: Queda 1 minuto")
            self.assertEqual(payload["body"], "El tiempo diario está cerca de su límite.")
        finally:
            fixture.close()

    def test_tui_uses_configured_spanish_labels(self):
        app = TuiApplication(Path("/tmp/unused.sock"))
        app.ui_language = "es"
        lines = app._view_lines(
            {
                "played_today_seconds": 65,
                "remaining_today_seconds": 120,
                "game": None,
                "timer": {"state": "idle", "remaining_seconds": 0},
                "restriction": {"effective_level": 0, "reason": "none"},
                "seconds_until_reset": 3600,
            }
        )
        self.assertTrue(lines[0].startswith("Jugado hoy:"))
        self.assertIn("inactivo", lines[3])

    def test_cli_help_can_use_spanish(self):
        help_text = build_parser("es").format_help()
        self.assertIn("Control local de tiempo de juego", help_text)
        self.assertIn("mostrar el estado actual", help_text)
