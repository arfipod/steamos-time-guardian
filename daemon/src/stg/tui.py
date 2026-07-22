"""Dependency-free Desktop Mode TUI with seven focused views."""

from __future__ import annotations

import asyncio
import curses
import json
from pathlib import Path
from typing import Any

from .i18n import (
    display_restriction_reason,
    display_scope,
    display_session_reason,
    display_timer_action,
    display_timer_state,
    format_duration,
    language,
    tr,
)
from .ipc import RpcError, UnixRpcClient
from .paths import AppPaths

VIEWS = ("summary", "timer", "daily", "weekly", "history", "settings", "diagnostics")
VIEW_LABELS = {
    "summary": "summary",
    "timer": "session_timer",
    "daily": "daily_limit_view",
    "weekly": "weekly",
    "history": "history",
    "settings": "settings",
    "diagnostics": "diagnostics",
}


class TuiApplication:
    def __init__(self, socket_path: Path, language_override: str | None = None):
        self.client = UnixRpcClient(socket_path)
        self.view = 0
        self.message = ""
        self.pending_level: int | None = None
        self.language_override = language_override
        self.ui_language = language(language_override)

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return asyncio.run(self.client.call(method, params))

    def run(self, screen: Any) -> None:
        curses.curs_set(0)
        screen.timeout(1000)
        while True:
            screen.erase()
            try:
                data = self._data_for_view()
                self._draw(screen, data)
            except RpcError as exc:
                self.message = tr(self.ui_language, "service_error", message=exc.message)
                self._draw(screen, {})
            key = screen.getch()
            if key in (ord("q"), 27):
                return
            if key in (curses.KEY_RIGHT, ord("l"), ord("]")):
                self.view = (self.view + 1) % len(VIEWS)
                self.pending_level = None
            elif key in (curses.KEY_LEFT, ord("h"), ord("[")):
                self.view = (self.view - 1) % len(VIEWS)
                self.pending_level = None
            elif ord("1") <= key <= ord("7"):
                self.view = key - ord("1")
                self.pending_level = None
            else:
                self._handle_action(key)

    def _data_for_view(self) -> dict[str, Any]:
        name = VIEWS[self.view]
        if self.language_override is None:
            self.ui_language = language(self.call("config.get").get("language"))
        if name in {"summary", "timer", "daily", "settings"}:
            return self.call("status.get")
        if name == "weekly":
            return self.call("summary.weekly")
        if name == "history":
            return self.call("history.list", {"limit": 20})
        if name == "diagnostics":
            return self.call("diagnostics.get")
        return {}

    def _draw(self, screen: Any, data: dict[str, Any]) -> None:
        height, width = screen.getmaxyx()
        title = "SteamOS Time Guardian"
        screen.addnstr(0, 2, title, max(0, width - 4), curses.A_BOLD)
        tabs = "  ".join(
            f"{i + 1}:{tr(self.ui_language, VIEW_LABELS[name])}" for i, name in enumerate(VIEWS)
        )
        screen.addnstr(2, 1, tabs, max(0, width - 2), curses.A_REVERSE)
        lines = self._view_lines(data)
        for row, line in enumerate(lines[: max(0, height - 7)], start=4):
            screen.addnstr(row, 2, line, max(0, width - 4))
        footer = self._footer()
        screen.addnstr(max(0, height - 2), 1, footer, max(0, width - 2), curses.A_DIM)
        if self.message:
            screen.addnstr(max(0, height - 1), 1, self.message, max(0, width - 2), curses.A_BOLD)
        screen.refresh()

    def _view_lines(self, data: dict[str, Any]) -> list[str]:
        view = VIEWS[self.view]
        if view == "summary":
            restriction = data.get("restriction", {})
            game = data.get("game") or {}
            next_warning = data.get("next_warning") or {}
            return [
                f"{tr(self.ui_language, 'played_today')}:    {format_duration(data.get('played_today_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'remaining_today')}: {format_duration(data.get('remaining_today_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'detected_game')}:   {game.get('name', tr(self.ui_language, 'none'))}",
                f"{tr(self.ui_language, 'timer')}:           {display_timer_state(data.get('timer', {}).get('state'), self.ui_language)} / {format_duration(data.get('timer', {}).get('remaining_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'restriction')}:     {tr(self.ui_language, 'level')} {restriction.get('effective_level', 0)} ({display_restriction_reason(restriction.get('reason'), self.ui_language)})",
                f"{tr(self.ui_language, 'next_warning')}:    {display_scope(next_warning.get('scope'), self.ui_language)} / {format_duration(next_warning.get('play_seconds_until'), self.ui_language)}",
                f"{tr(self.ui_language, 'next_reset')}:      {format_duration(data.get('seconds_until_reset'), self.ui_language)}",
            ]
        if view == "timer":
            timer = data.get("timer", {})
            return [
                f"{tr(self.ui_language, 'state')}:      {display_timer_state(timer.get('state'), self.ui_language)}",
                f"{tr(self.ui_language, 'remaining')}:  {format_duration(timer.get('remaining_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'configured')}: {format_duration(timer.get('configured_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'action')}:     {display_timer_action(timer.get('action'), self.ui_language)}",
                "",
                tr(self.ui_language, "timer_controls"),
            ]
        if view == "daily":
            return [
                f"{tr(self.ui_language, 'accounting_day')}: {data.get('day_key', '-')}",
                f"{tr(self.ui_language, 'limit')}:          {format_duration(data.get('daily_limit_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'exceptional_time')}:     {format_duration(data.get('daily_adjustment_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'played')}:         {format_duration(data.get('played_today_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'remaining')}:      {format_duration(data.get('remaining_today_seconds'), self.ui_language)}",
                f"{tr(self.ui_language, 'allowed_period')}: {tr(self.ui_language, 'yes' if data.get('within_allowed_period') else 'no')}",
                "",
                tr(self.ui_language, "grant_hint"),
            ]
        if view == "weekly":
            lines = [
                f"{tr(self.ui_language, 'week')}: {data.get('start_day', '-')} → {data.get('end_day', '-')}",
                f"{tr(self.ui_language, 'total')}: {format_duration(data.get('total_seconds'), self.ui_language)}",
                "",
            ]
            lines.extend(
                f"{day.get('day_key')}: {format_duration(day.get('total_seconds'), self.ui_language)}"
                for day in data.get("days", [])
            )
            return lines
        if view == "history":
            lines = [f"{tr(self.ui_language, 'recent_sessions')}:"]
            for session in data.get("sessions", []):
                lines.append(
                    f"{session.get('day_key')}  {session.get('app_name')}  "
                    f"{format_duration(session.get('duration_seconds'), self.ui_language)}  {display_session_reason(session.get('reason'), self.ui_language)}"
                )
            return lines if data.get("sessions") else [tr(self.ui_language, "no_history")]
        if view == "settings":
            restriction = data.get("restriction", {})
            return [
                f"{tr(self.ui_language, 'configured_restriction_level')}: {restriction.get('configured_level', 0)}",
                f"{tr(self.ui_language, 'force_kill')}: {tr(self.ui_language, 'enabled' if restriction.get('force_kill_enabled') else 'disabled')}",
                "",
                tr(self.ui_language, "level_hint"),
                tr(self.ui_language, "schedule_hint"),
            ]
        if view == "diagnostics":
            database = data.get("database", {})
            native = data.get("native_notifications", {})
            return [
                f"{tr(self.ui_language, 'version')}:              {data.get('project_version', '-')}",
                f"{tr(self.ui_language, 'python')}:               {data.get('python_version', '-')}",
                f"{tr(self.ui_language, 'detector')}:             {data.get('detector', '-')}",
                f"{tr(self.ui_language, 'database_quick_check')}: {database.get('quick_check', '-')}",
                f"{tr(self.ui_language, 'database_schema')}:            {database.get('schema_version', '-')}",
                f"{tr(self.ui_language, 'decky_connected')}:      {data.get('decky_plugin_recent', False)}",
                f"{tr(self.ui_language, 'notify_send')}:           {native.get('notify_send_available', False)}",
                f"{tr(self.ui_language, 'session_type')}:          {data.get('session_type', '-')}",
            ]
        return [json.dumps(data, indent=2)]

    def _footer(self) -> str:
        return tr(self.ui_language, "footer")

    def _handle_action(self, key: int) -> None:
        self.message = ""
        try:
            if VIEWS[self.view] == "timer":
                if key in (ord("s"), ord("S")):
                    self.call("timer.start", {"seconds": 1800})
                    self.message = tr(self.ui_language, "timer_started")
                elif key in (ord("p"), ord("P")):
                    self.call("timer.pause")
                    self.message = tr(self.ui_language, "timer_paused")
                elif key in (ord("r"), ord("R")):
                    self.call("timer.resume")
                    self.message = tr(self.ui_language, "timer_resumed")
                elif key in (ord("c"), ord("C")):
                    self.call("timer.cancel")
                    self.message = tr(self.ui_language, "timer_cancelled")
                elif key == ord("+"):
                    self.call("timer.adjust", {"seconds": 300})
                    self.message = tr(self.ui_language, "minutes_added")
                elif key == ord("-"):
                    self.call("timer.adjust", {"seconds": -300})
                    self.message = tr(self.ui_language, "minutes_removed")
            elif VIEWS[self.view] == "daily" and key in (ord("b"), ord("B")):
                self.call("daily.grant", {"seconds": 900, "reason": "Desktop TUI exceptional time"})
                self.message = tr(self.ui_language, "daily_time_added")
            elif VIEWS[self.view] == "settings" and key in (ord("l"), ord("L")):
                status = self.call("status.get")
                level = (int(status["restriction"]["configured_level"]) + 1) % 4
                if level >= 2 and self.pending_level != level:
                    self.pending_level = level
                    self.message = tr(self.ui_language, "confirm_level", level=level)
                    return
                self.call("config.update", {"patch": {"restriction": {"level": level}}})
                self.pending_level = None
                self.message = tr(self.ui_language, "level_set", level=level)
        except RpcError as exc:
            self.message = tr(self.ui_language, "action_failed", message=exc.message)


def run_tui(socket_path: Path | None = None, language_override: str | None = None) -> None:
    path = socket_path or AppPaths.from_environment().socket_file
    app = TuiApplication(path, language_override)
    curses.wrapper(app.run)
