"""Dependency-free Desktop Mode TUI with seven focused views."""

from __future__ import annotations

import asyncio
import curses
import json
from pathlib import Path
from typing import Any

from .ipc import RpcError, UnixRpcClient
from .paths import AppPaths

VIEWS = ("Summary", "Timer", "Daily limit", "Weekly", "History", "Settings", "Diagnostics")


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "Unlimited"
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:d}h {minutes:02d}m {secs:02d}s" if hours else f"{minutes:d}m {secs:02d}s"


class TuiApplication:
    def __init__(self, socket_path: Path):
        self.client = UnixRpcClient(socket_path)
        self.view = 0
        self.message = ""
        self.pending_level: int | None = None

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
                self.message = f"Service error: {exc.message}"
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
        if name in {"Summary", "Timer", "Daily limit", "Settings"}:
            return self.call("status.get")
        if name == "Weekly":
            return self.call("summary.weekly")
        if name == "History":
            return self.call("history.list", {"limit": 20})
        if name == "Diagnostics":
            return self.call("diagnostics.get")
        return {}

    def _draw(self, screen: Any, data: dict[str, Any]) -> None:
        height, width = screen.getmaxyx()
        title = "SteamOS Time Guardian"
        screen.addnstr(0, 2, title, max(0, width - 4), curses.A_BOLD)
        tabs = "  ".join(f"{i + 1}:{name}" for i, name in enumerate(VIEWS))
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
        if view == "Summary":
            restriction = data.get("restriction", {})
            game = data.get("game") or {}
            next_warning = data.get("next_warning") or {}
            return [
                f"Played today:    {format_duration(data.get('played_today_seconds'))}",
                f"Remaining today: {format_duration(data.get('remaining_today_seconds'))}",
                f"Detected game:   {game.get('name', 'None')}",
                f"Timer:           {data.get('timer', {}).get('state', 'unknown')} / {format_duration(data.get('timer', {}).get('remaining_seconds'))}",
                f"Restriction:     level {restriction.get('effective_level', 0)} ({restriction.get('reason', 'none')})",
                f"Next warning:    {next_warning.get('scope', 'none')} / {format_duration(next_warning.get('play_seconds_until'))}",
                f"Next reset:      {format_duration(data.get('seconds_until_reset'))}",
            ]
        if view == "Timer":
            timer = data.get("timer", {})
            return [
                f"State:      {timer.get('state', 'unknown')}",
                f"Remaining:  {format_duration(timer.get('remaining_seconds'))}",
                f"Configured: {format_duration(timer.get('configured_seconds'))}",
                f"Action:     {timer.get('action', 'inherit')}",
                "",
                "S starts 30m · P pauses · R resumes · C cancels · +/- changes 5m",
            ]
        if view == "Daily limit":
            return [
                f"Accounting day: {data.get('day_key', '-')}",
                f"Limit:          {format_duration(data.get('daily_limit_seconds'))}",
                f"Extra time:     {format_duration(data.get('daily_adjustment_seconds'))}",
                f"Played:         {format_duration(data.get('played_today_seconds'))}",
                f"Remaining:      {format_duration(data.get('remaining_today_seconds'))}",
                f"Allowed period: {'yes' if data.get('within_allowed_period') else 'no'}",
                "",
                "B grants 15 exceptional minutes for today.",
            ]
        if view == "Weekly":
            lines = [
                f"Week: {data.get('start_day', '-')} → {data.get('end_day', '-')}",
                f"Total: {format_duration(data.get('total_seconds'))}",
                "",
            ]
            lines.extend(
                f"{day.get('day_key')}: {format_duration(day.get('total_seconds'))}"
                for day in data.get("days", [])
            )
            return lines
        if view == "History":
            lines = ["Recent sessions:"]
            for session in data.get("sessions", []):
                lines.append(
                    f"{session.get('day_key')}  {session.get('app_name')}  "
                    f"{format_duration(session.get('duration_seconds'))}  {session.get('reason') or 'open'}"
                )
            return lines or ["No history"]
        if view == "Settings":
            restriction = data.get("restriction", {})
            return [
                f"Configured restriction level: {restriction.get('configured_level', 0)}",
                f"Force kill: {'enabled' if restriction.get('force_kill_enabled') else 'disabled'}",
                "",
                "L cycles restriction levels 0–3.",
                "Edit the complete weekly schedule in config.json or with the CLI.",
            ]
        if view == "Diagnostics":
            database = data.get("database", {})
            native = data.get("native_notifications", {})
            return [
                f"Version:              {data.get('project_version', '-')}",
                f"Python:               {data.get('python_version', '-')}",
                f"Detector:             {data.get('detector', '-')}",
                f"Database quick_check: {database.get('quick_check', '-')}",
                f"DB schema:            {database.get('schema_version', '-')}",
                f"Decky connected:      {data.get('decky_plugin_recent', False)}",
                f"notify-send:           {native.get('notify_send_available', False)}",
                f"Session type:          {data.get('session_type', '-')}",
            ]
        return [json.dumps(data, indent=2)]

    def _footer(self) -> str:
        return "←/→ change view · 1–7 jump · Q quit"

    def _handle_action(self, key: int) -> None:
        self.message = ""
        try:
            if VIEWS[self.view] == "Timer":
                if key in (ord("s"), ord("S")):
                    self.call("timer.start", {"seconds": 1800})
                    self.message = "30-minute timer started"
                elif key in (ord("p"), ord("P")):
                    self.call("timer.pause")
                    self.message = "Timer paused"
                elif key in (ord("r"), ord("R")):
                    self.call("timer.resume")
                    self.message = "Timer resumed"
                elif key in (ord("c"), ord("C")):
                    self.call("timer.cancel")
                    self.message = "Timer cancelled"
                elif key == ord("+"):
                    self.call("timer.adjust", {"seconds": 300})
                    self.message = "Added 5 minutes"
                elif key == ord("-"):
                    self.call("timer.adjust", {"seconds": -300})
                    self.message = "Removed 5 minutes"
            elif VIEWS[self.view] == "Daily limit" and key in (ord("b"), ord("B")):
                self.call("daily.grant", {"seconds": 900, "reason": "Desktop TUI exceptional time"})
                self.message = "Added 15 minutes for today"
            elif VIEWS[self.view] == "Settings" and key in (ord("l"), ord("L")):
                status = self.call("status.get")
                level = (int(status["restriction"]["configured_level"]) + 1) % 4
                if level >= 2 and self.pending_level != level:
                    self.pending_level = level
                    self.message = f"Press L again to confirm restriction level {level}"
                    return
                self.call("config.update", {"patch": {"restriction": {"level": level}}})
                self.pending_level = None
                self.message = f"Restriction level set to {level}"
        except RpcError as exc:
            self.message = f"Action failed: {exc.message}"


def run_tui(socket_path: Path | None = None) -> None:
    path = socket_path or AppPaths.from_environment().socket_file
    app = TuiApplication(path)
    curses.wrapper(app.run)
