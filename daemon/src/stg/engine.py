"""Core time-accounting state machine.

The engine is deliberately independent from systemd, Decky, Unix sockets, and process signals.
All mutating calls are serialized by the service layer, making it straightforward to test.
"""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from .clock import Clock
from .models import DomainEvent, GameIdentity, RestrictionReason, TimerSnapshot, TimerState
from .schedule import (
    accounting_day,
    accounting_day_key,
    accounting_day_start,
    limit_for_day,
    local_datetime,
    seconds_until_reset,
    within_allowed_period,
)
from .storage import DatabaseError, Storage, utc_iso

_TIMER_ACTION_LEVEL = {
    "inherit": None,
    "notify_only": 0,
    "soft": 1,
    "close": 2,
    "block": 3,
}


class DomainError(ValueError):
    """A requested state transition is invalid or unsafe."""


class GuardianEngine:
    def __init__(self, storage: Storage, config: dict[str, Any], clock: Clock):
        self.storage = storage
        self.config = copy.deepcopy(config)
        self.clock = clock
        now = self.clock.now_utc()
        self.day_key = self._day_key(now)
        self.played_today = self.storage.usage_for_day(self.day_key)
        self.current_game: GameIdentity | None = None
        self.session_id: str | None = None
        self.session_duration = 0.0
        self.timer = self.storage.load_timer()
        self.suspended = False
        self.restriction_reason = RestrictionReason.NONE
        self.restriction_level = 0
        self._last_tick_mono = self.clock.monotonic()
        self._last_tick_wall = now
        self._last_checkpoint_mono = self._last_tick_mono
        self._last_timer_persist_mono = self._last_tick_mono
        self._last_offset_seconds = self._utc_offset(now)
        self._initial_events: list[DomainEvent] = []
        recovered = self.storage.recover_open_session(now)
        if recovered:
            self._initial_events.append(
                self._event(
                    "session.recovered",
                    {"session_id": recovered["id"], "duration_seconds": int(recovered["duration_seconds"])},
                    severity="warning",
                )
            )
        if self.timer.state == TimerState.RUNNING:
            self.timer.state = TimerState.PAUSED
            self.timer.updated_at = utc_iso(now)
            self.storage.save_timer(self.timer)
            self._initial_events.append(
                self._event(
                    "timer.paused_after_restart",
                    {"remaining_seconds": int(self.timer.remaining_seconds)},
                    severity="warning",
                )
            )
        self._refresh_restriction(now, emit=False)

    def take_initial_events(self) -> list[DomainEvent]:
        events, self._initial_events = self._initial_events, []
        return events

    def update_config(self, config: dict[str, Any]) -> list[DomainEvent]:
        events = self.tick()
        self.config = copy.deepcopy(config)
        now = self.clock.now_utc()
        new_day_key = self._day_key(now)
        if new_day_key != self.day_key:
            events.extend(self._roll_day(now, new_day_key))
        events.extend(self._refresh_restriction(now, emit=True))
        events.append(self._event("config.updated", {"schema_version": config["schema_version"]}))
        return events

    def tick(self) -> list[DomainEvent]:
        now = self.clock.now_utc()
        mono = self.clock.monotonic()
        mono_delta = max(0.0, mono - self._last_tick_mono)
        wall_delta = (now - self._last_tick_wall).total_seconds()
        discrepancy = wall_delta - mono_delta
        events: list[DomainEvent] = []

        if discrepancy > 30:
            events.extend(self._record_suspend_gap(now, discrepancy))
        elif abs(discrepancy) > 5:
            events.append(
                self._record_event(
                    "clock.changed",
                    {
                        "wall_delta_seconds": round(wall_delta, 3),
                        "monotonic_delta_seconds": round(mono_delta, 3),
                    },
                    severity="warning",
                )
            )
        offset = self._utc_offset(now)
        if offset != self._last_offset_seconds:
            events.append(
                self._record_event(
                    "timezone.offset_changed",
                    {"old_offset_seconds": self._last_offset_seconds, "new_offset_seconds": offset},
                    severity="warning",
                )
            )
            self._last_offset_seconds = offset

        new_day_key = self._day_key(now)
        split_before = mono_delta
        split_after = 0.0
        boundary = now
        if new_day_key != self.day_key:
            try:
                boundary = accounting_day_start(
                    date.fromisoformat(new_day_key),
                    self.config["daily_limits"]["reset_at"],
                    self.config["daily_limits"]["timezone"],
                )
            except ValueError:
                boundary = now
            split_before, split_after = self._split_elapsed_at_boundary(
                mono_delta,
                self._last_tick_wall,
                now,
                boundary,
            )

        # CLOCK_MONOTONIC excludes suspend on Linux, so only active elapsed time is counted.
        if not self.suspended:
            self._account_game_elapsed(split_before)

        if new_day_key != self.day_key:
            events.extend(self._roll_day(boundary, new_day_key))
            if not self.suspended:
                self._account_game_elapsed(split_after)

        if (
            self.timer.state == TimerState.RUNNING
            and not self.suspended
            and (not self.config["timer"]["count_only_while_playing"] or self.current_game is not None)
        ):
            self.timer.remaining_seconds = max(0.0, self.timer.remaining_seconds - mono_delta)
            if self.timer.remaining_seconds <= 0:
                self.timer.state = TimerState.EXPIRED
                self.timer.updated_at = utc_iso(now)
                self.storage.save_timer(self.timer)
                events.append(self._record_event("timer.expired", {}, severity="warning"))

        checkpoint_seconds = self.config["history"]["checkpoint_seconds"]
        if self.session_id and mono - self._last_checkpoint_mono >= checkpoint_seconds:
            self.storage.checkpoint_session(self.session_id, self.session_duration, now)
            self._last_checkpoint_mono = mono
        if self.timer.state == TimerState.RUNNING and mono - self._last_timer_persist_mono >= checkpoint_seconds:
            self.timer.updated_at = utc_iso(now)
            self.storage.save_timer(self.timer)
            self._last_timer_persist_mono = mono

        events.extend(self._warning_events(now))
        events.extend(self._refresh_restriction(now, emit=True))
        self._last_tick_mono = mono
        self._last_tick_wall = now
        return events

    def set_game(self, game: GameIdentity, *, reason: str = "detected") -> list[DomainEvent]:
        self._validate_game(game)
        now = self.clock.now_utc()
        events = self.tick()
        if self.current_game and self._same_game(self.current_game, game):
            self.current_game = game
            events.append(self._event("game.metadata_updated", game.to_dict()))
            return events
        if self.current_game:
            events.extend(self._close_current_game(now, "game_changed"))
        self.current_game = game
        try:
            self.session_id = self.storage.open_session(self.day_key, game, now)
        except DatabaseError as exc:
            self.current_game = None
            raise DomainError(str(exc)) from exc
        self.session_duration = 0.0
        self._last_checkpoint_mono = self.clock.monotonic()
        events.append(
            self._event(
                "game.started",
                {"game": game.to_dict(), "session_id": self.session_id, "reason": reason},
            )
        )
        if self.restriction_level >= 2:
            kind = (
                "enforcement.new_game_blocked"
                if self.restriction_level >= 3
                else "enforcement.game_started_while_restricted"
            )
            events.append(
                self._event(
                    kind,
                    {
                        "game": game.to_dict(),
                        "launch_grace_seconds": self.config["restriction"]["launch_grace_seconds"],
                    },
                    severity="warning",
                )
            )
        return events

    def stop_game(self, *, reason: str = "detected_exit") -> list[DomainEvent]:
        now = self.clock.now_utc()
        events = self.tick()
        events.extend(self._close_current_game(now, reason))
        events.extend(self._refresh_restriction(now, emit=True))
        return events

    def suspend(self, source: str = "detector") -> list[DomainEvent]:
        events = self.tick()
        if not self.suspended:
            self.suspended = True
            events.append(self._record_event("system.suspended", {"source": source}))
        return events

    def resume(self, source: str = "detector") -> list[DomainEvent]:
        now = self.clock.now_utc()
        # Reset baselines before the next tick so the suspend interval is not misclassified.
        self._last_tick_wall = now
        self._last_tick_mono = self.clock.monotonic()
        events: list[DomainEvent] = []
        new_day_key = self._day_key(now)
        if new_day_key != self.day_key:
            events.extend(self._roll_day(now, new_day_key))
        if self.suspended:
            self.suspended = False
            events.append(self._record_event("system.resumed", {"source": source}))
        return events

    def start_timer(self, seconds: int, action: str = "inherit") -> list[DomainEvent]:
        events = self.tick()
        if self.restriction_level >= 1:
            raise DomainError("cannot start a timer while play is restricted")
        if not 60 <= seconds <= 24 * 3600:
            raise DomainError("timer duration must be between 60 seconds and 24 hours")
        if action not in _TIMER_ACTION_LEVEL:
            raise DomainError(f"unsupported timer action: {action}")
        now = self.clock.now_utc()
        self.timer = TimerSnapshot(
            state=TimerState.RUNNING,
            configured_seconds=seconds,
            remaining_seconds=float(seconds),
            action=action,
            generation=str(uuid4()),
            started_at=utc_iso(now),
            updated_at=utc_iso(now),
        )
        self.storage.save_timer(self.timer)
        self.storage.clear_notification_scope("timer", self.timer.generation or "")
        events.append(self._record_event("timer.started", self.timer.to_dict()))
        return events

    def pause_timer(self) -> list[DomainEvent]:
        events = self.tick()
        if self.timer.state != TimerState.RUNNING:
            raise DomainError("timer is not running")
        self.timer.state = TimerState.PAUSED
        self.timer.updated_at = utc_iso(self.clock.now_utc())
        self.storage.save_timer(self.timer)
        events.append(self._record_event("timer.paused", self.timer.to_dict()))
        return events

    def resume_timer(self) -> list[DomainEvent]:
        events = self.tick()
        if self.restriction_level >= 1:
            raise DomainError("cannot resume a timer while play is restricted")
        if self.timer.state != TimerState.PAUSED:
            raise DomainError("timer is not paused")
        self.timer.state = TimerState.RUNNING
        self.timer.updated_at = utc_iso(self.clock.now_utc())
        self.storage.save_timer(self.timer)
        events.append(self._record_event("timer.resumed", self.timer.to_dict()))
        return events

    def cancel_timer(self) -> list[DomainEvent]:
        events = self.tick()
        if self.timer.state == TimerState.IDLE:
            return events
        previous = self.timer.to_dict()
        self.timer = TimerSnapshot()
        self.storage.save_timer(self.timer)
        events.append(self._record_event("timer.cancelled", {"previous": previous}))
        events.extend(self._refresh_restriction(self.clock.now_utc(), emit=True))
        return events

    def adjust_timer(self, seconds: int) -> list[DomainEvent]:
        events = self.tick()
        if self.timer.state == TimerState.IDLE:
            raise DomainError("there is no active timer")
        if not -24 * 3600 <= seconds <= 24 * 3600:
            raise DomainError("timer adjustment must be between -24h and +24h")
        if seconds == 0:
            raise DomainError("timer adjustment must not be zero")
        self.timer.remaining_seconds = max(0.0, min(24 * 3600, self.timer.remaining_seconds + seconds))
        if self.timer.remaining_seconds == 0:
            self.timer.state = TimerState.EXPIRED
        elif self.timer.state == TimerState.EXPIRED:
            self.timer.state = TimerState.PAUSED
        self.timer.updated_at = utc_iso(self.clock.now_utc())
        self.storage.save_timer(self.timer)
        if seconds > 0 and self.timer.generation:
            self.storage.clear_notification_scope("timer", self.timer.generation)
        events.append(
            self._record_event("timer.adjusted", {"seconds": seconds, "timer": self.timer.to_dict()})
        )
        events.extend(self._refresh_restriction(self.clock.now_utc(), emit=True))
        return events

    def grant_daily_time(self, seconds: int, reason: str) -> list[DomainEvent]:
        events = self.tick()
        if not reason.strip():
            raise DomainError("an adjustment reason is required")
        if seconds == 0:
            raise DomainError("daily adjustment must not be zero")
        self.storage.grant_adjustment(self.day_key, seconds, reason.strip(), self.clock.now_utc())
        if seconds > 0:
            self.storage.clear_notification_scope("daily", self.day_key)
        events.append(
            self._event(
                "daily.adjusted",
                {"day_key": self.day_key, "seconds": seconds, "reason": reason.strip()},
            )
        )
        events.extend(self._refresh_restriction(self.clock.now_utc(), emit=True))
        return events

    def shutdown(self, reason: str = "service_shutdown") -> list[DomainEvent]:
        now = self.clock.now_utc()
        events = self.tick()
        if self.session_id:
            self.storage.checkpoint_session(self.session_id, self.session_duration, now)
            events.extend(self._close_current_game(now, reason))
        if self.timer.state == TimerState.RUNNING:
            self.timer.updated_at = utc_iso(now)
            self.storage.save_timer(self.timer)
        return events

    def status(self) -> dict[str, Any]:
        now = self.clock.now_utc()
        limit = self._effective_daily_limit(now)
        remaining = None if limit is None else max(0, int(round(limit - self.played_today)))
        next_warning = self._next_warning_status(remaining)
        return {
            "schema_version": 1,
            "now": utc_iso(now),
            "day_key": self.day_key,
            "played_today_seconds": max(0, int(round(self.played_today))),
            "daily_limit_seconds": limit,
            "daily_adjustment_seconds": self.storage.adjustment_for_day(self.day_key),
            "remaining_today_seconds": remaining,
            "seconds_until_reset": seconds_until_reset(
                now,
                self.config["daily_limits"]["reset_at"],
                self.config["daily_limits"]["timezone"],
            ),
            "within_allowed_period": (
                not self.config["daily_limits"]["enabled"]
                or within_allowed_period(self.config, now)
            ),
            "game": self.current_game.to_dict() if self.current_game else None,
            "timer": self.timer.to_dict(),
            "next_warning_seconds": (
                next_warning["play_seconds_until"] if next_warning is not None else None
            ),
            "next_warning": next_warning,
            "restriction": {
                "configured_level": self.config["restriction"]["level"],
                "effective_level": self.restriction_level,
                "reason": self.restriction_reason.value,
                "force_kill_enabled": self.config["restriction"]["force_kill_enabled"],
            },
            "suspended": self.suspended,
        }

    def _warning_events(self, now: datetime) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        thresholds = [minutes * 60 for minutes in self.config["warnings"]["threshold_minutes"]]
        daily_limit = self._effective_daily_limit(now)
        daily_remaining = None if daily_limit is None else max(0, int(daily_limit - self.played_today))
        if daily_remaining is not None:
            events.extend(self._threshold_events("daily", self.day_key, daily_remaining, thresholds, now))
        if self.timer.state in {TimerState.RUNNING, TimerState.PAUSED, TimerState.EXPIRED} and self.timer.generation:
            timer_remaining = max(0, int(self.timer.remaining_seconds))
            events.extend(
                self._threshold_events("timer", self.timer.generation, timer_remaining, thresholds, now)
            )
        return events

    def _threshold_events(
        self,
        scope: str,
        scope_key: str,
        remaining: int,
        thresholds: list[int],
        now: datetime,
    ) -> list[DomainEvent]:
        due = [threshold for threshold in thresholds if 0 < remaining <= threshold]
        if remaining == 0 and self.config["warnings"]["notify_at_exhaustion"]:
            due.append(0)
        events: list[DomainEvent] = []
        # Mark all crossed thresholds, but emit only the smallest currently due to avoid a burst after restart.
        newly_marked: list[int] = []
        for threshold in due:
            if self.storage.mark_notification(scope, scope_key, threshold, now):
                newly_marked.append(threshold)
        if newly_marked:
            threshold = min(newly_marked)
            if threshold == 0:
                title = "Play time exhausted"
                body = "The configured play-time allowance has been used."
                urgency = "critical"
            else:
                minutes = max(1, threshold // 60)
                title = f"{minutes} minute{'s' if minutes != 1 else ''} remaining"
                body = f"{scope.capitalize()} allowance is nearing its limit."
                urgency = "normal" if minutes > 5 else "critical"
            payload = {
                "scope": scope,
                "scope_key": scope_key,
                "remaining_seconds": remaining,
                "threshold_seconds": threshold,
                "title": title,
                "body": body,
                "urgency": urgency,
                "persistent": threshold == 0,
            }
            events.append(self._record_event("notification.warning", payload, severity="warning"))
        return events

    def _refresh_restriction(self, now: datetime, *, emit: bool) -> list[DomainEvent]:
        reason = RestrictionReason.NONE
        level = 0
        configured_level = int(self.config["restriction"]["level"])
        daily_limit = self._effective_daily_limit(now)
        if self.timer.state == TimerState.EXPIRED:
            reason = RestrictionReason.TIMER_EXPIRED
            override = _TIMER_ACTION_LEVEL.get(self.timer.action)
            level = configured_level if override is None else int(override)
        elif daily_limit is not None and self.played_today >= daily_limit:
            reason = RestrictionReason.DAILY_LIMIT
            level = configured_level
        elif self.config["daily_limits"]["enabled"] and not within_allowed_period(self.config, now):
            reason = RestrictionReason.OUTSIDE_ALLOWED_PERIOD
            level = configured_level
        old_reason, old_level = self.restriction_reason, self.restriction_level
        self.restriction_reason, self.restriction_level = reason, level
        if not emit or (old_reason == reason and old_level == level):
            return []
        payload = {
            "old_reason": old_reason.value,
            "reason": reason.value,
            "old_level": old_level,
            "level": level,
            "grace_seconds": self.config["restriction"]["grace_seconds"],
            "game": self.current_game.to_dict() if self.current_game else None,
            "persistent_notice_required": (
                reason == RestrictionReason.OUTSIDE_ALLOWED_PERIOD
                or not self.config["warnings"]["notify_at_exhaustion"]
            ),
        }
        if reason == RestrictionReason.NONE:
            kind = "restriction.cleared"
            severity = "info"
        elif level == 0:
            # Tracking-only mode still records exhaustion, but must not look like a clear.
            kind = "allowance.exhausted"
            severity = "warning"
        else:
            kind = "restriction.activated"
            severity = "warning"
        return [self._record_event(kind, payload, severity=severity)]

    def _roll_day(self, now: datetime, new_day_key: str) -> list[DomainEvent]:
        old_day = self.day_key
        events: list[DomainEvent] = []
        if self.current_game and self.session_id:
            self.storage.close_session(self.session_id, self.session_duration, now, "daily_reset")
            events.append(
                self._event(
                    "session.rotated_at_daily_reset",
                    {"old_day_key": old_day, "new_day_key": new_day_key},
                )
            )
            self.session_id = self.storage.open_session(new_day_key, self.current_game, now)
            self.session_duration = 0.0
            self._last_checkpoint_mono = self.clock.monotonic()
        self.day_key = new_day_key
        self.played_today = self.storage.usage_for_day(new_day_key)
        self.storage.enforce_retention(self.config["history"]["retention_days"], now)
        events.append(
            self._record_event(
                "daily.reset",
                {
                    "old_day_key": old_day,
                    "new_day_key": new_day_key,
                    "boundary_at": utc_iso(now),
                },
            )
        )
        return events

    def _record_suspend_gap(self, now: datetime, discrepancy: float) -> list[DomainEvent]:
        payload = {"inferred_gap_seconds": int(discrepancy), "source": "wall_vs_monotonic"}
        self.storage.record_event("system.suspend_inferred", now, payload)
        self.storage.record_event("system.resume_inferred", now, payload)
        return [
            self._event("system.suspend_inferred", payload, severity="warning"),
            self._event("system.resume_inferred", payload, severity="warning"),
        ]

    def _close_current_game(self, now: datetime, reason: str) -> list[DomainEvent]:
        if not self.current_game or not self.session_id:
            self.current_game = None
            self.session_id = None
            self.session_duration = 0.0
            return []
        game = self.current_game
        session_id = self.session_id
        duration = self.session_duration
        self.storage.close_session(session_id, duration, now, reason)
        self.current_game = None
        self.session_id = None
        self.session_duration = 0.0
        return [
            self._event(
                "game.stopped",
                {
                    "game": game.to_dict(),
                    "session_id": session_id,
                    "duration_seconds": int(round(duration)),
                    "reason": reason,
                },
            )
        ]

    def _effective_daily_limit(self, now: datetime) -> int | None:
        if not self.config["daily_limits"]["enabled"]:
            return None
        day = accounting_day(
            now,
            self.config["daily_limits"]["reset_at"],
            self.config["daily_limits"]["timezone"],
        )
        base = limit_for_day(self.config, day)
        if base is None:
            return None
        return max(0, base + self.storage.adjustment_for_day(self.day_key))

    def _day_key(self, now: datetime) -> str:
        return accounting_day_key(
            now,
            self.config["daily_limits"]["reset_at"],
            self.config["daily_limits"]["timezone"],
        )

    def _next_warning_status(self, daily_remaining: int | None) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        if daily_remaining is not None:
            candidate = self._warning_candidate("daily", self.day_key, daily_remaining)
            if candidate:
                candidates.append(candidate)
        if self.timer.state == TimerState.RUNNING and self.timer.generation:
            timer_counts = (
                not self.config["timer"]["count_only_while_playing"]
                or self.current_game is not None
            )
            if timer_counts:
                candidate = self._warning_candidate(
                    "timer",
                    self.timer.generation,
                    max(0, int(self.timer.remaining_seconds)),
                )
                if candidate:
                    candidates.append(candidate)
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item["play_seconds_until"], item["threshold_seconds"]))

    def _warning_candidate(
        self, scope: str, scope_key: str, remaining: int
    ) -> dict[str, Any] | None:
        thresholds = [minutes * 60 for minutes in self.config["warnings"]["threshold_minutes"]]
        if self.config["warnings"]["notify_at_exhaustion"]:
            thresholds.append(0)
        marked = self.storage.notification_thresholds(scope, scope_key)
        candidates = [threshold for threshold in thresholds if threshold not in marked and threshold <= remaining]
        if not candidates:
            return None
        threshold = max(candidates)
        return {
            "scope": scope,
            "threshold_seconds": threshold,
            "play_seconds_until": max(0, remaining - threshold),
        }

    def _utc_offset(self, now: datetime) -> int:
        local = local_datetime(now, self.config["daily_limits"]["timezone"])
        offset = local.utcoffset()
        return int(offset.total_seconds()) if offset else 0

    def _account_game_elapsed(self, seconds: float) -> None:
        if self.current_game and seconds > 0:
            self.played_today += seconds
            self.session_duration += seconds

    @staticmethod
    def _split_elapsed_at_boundary(
        monotonic_delta: float,
        previous_wall: datetime,
        current_wall: datetime,
        boundary: datetime,
    ) -> tuple[float, float]:
        wall_delta = (current_wall - previous_wall).total_seconds()
        if monotonic_delta <= 0:
            return 0.0, 0.0
        if wall_delta <= 0 or boundary <= previous_wall:
            # When a clock jump or long suspend makes attribution ambiguous, assign active
            # monotonic time to the current accounting day rather than inventing old-day use.
            return 0.0, monotonic_delta
        if boundary >= current_wall:
            return monotonic_delta, 0.0
        ratio = max(0.0, min(1.0, (boundary - previous_wall).total_seconds() / wall_delta))
        before = monotonic_delta * ratio
        return before, monotonic_delta - before

    @staticmethod
    def _same_game(left: GameIdentity, right: GameIdentity) -> bool:
        if left.app_id and right.app_id:
            return left.app_id == right.app_id
        return left.name.casefold() == right.name.casefold()

    @staticmethod
    def _validate_game(game: GameIdentity) -> None:
        if not game.name.strip() or len(game.name) > 200:
            raise DomainError("game name must contain 1..200 characters")
        if game.app_id is not None and (len(game.app_id) > 32 or not game.app_id.isdigit()):
            raise DomainError("app_id must be a decimal string")
        if any(pid <= 0 for pid in game.pids):
            raise DomainError("PIDs must be positive")

    def _event(self, kind: str, payload: dict[str, Any], severity: str = "info") -> DomainEvent:
        return DomainEvent(kind=kind, occurred_at=self.clock.now_utc(), payload=payload, severity=severity)

    def _record_event(self, kind: str, payload: dict[str, Any], severity: str = "info") -> DomainEvent:
        event = self._event(kind, payload, severity)
        app_id = self.current_game.app_id if self.current_game else None
        self.storage.record_event(kind, event.occurred_at, payload, session_id=self.session_id, app_id=app_id)
        return event
