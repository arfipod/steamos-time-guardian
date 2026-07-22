from __future__ import annotations

import unittest

from stg.detectors.base import DetectorEventType
from stg.detectors.steam_log import SteamLogParser


class SteamLogParserTests(unittest.TestCase):
    def test_tracks_multi_process_game_until_running_list_removed(self):
        parser = SteamLogParser({"3405690": "Fixture Game"})
        first = parser.feed_line("[2026-07-20] AppID 3405690 adding PID 100 as a tracked process")
        second = parser.feed_line("[2026-07-20] AppID 3405690 adding PID 101 as a tracked process")
        parser.feed_line("[2026-07-20] AppID 3405690 no longer tracking PID 100, exit code 0")
        stopped = parser.feed_line("[2026-07-20] Remove 3405690 from running list")
        self.assertEqual(first[0].type, DetectorEventType.STARTED)
        self.assertEqual(first[0].game.name, "Fixture Game")
        self.assertEqual(second, [])
        self.assertEqual(stopped[0].type, DetectorEventType.STOPPED)

    def test_ignores_unrelated_lines(self):
        parser = SteamLogParser()
        self.assertEqual(parser.feed_line("ordinary Steam log message"), [])

    def test_handles_non_steam_zero_app_id_without_process_names(self):
        parser = SteamLogParser()
        events = parser.feed_line("AppID 0 adding PID 404 as a tracked process")
        self.assertEqual(events[0].game.app_id, "0")
        self.assertEqual(events[0].game.source, "steam_log")
