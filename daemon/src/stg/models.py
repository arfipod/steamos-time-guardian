"""Typed domain models shared by the daemon, detector, and IPC layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TimerState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    EXPIRED = "expired"


class RestrictionReason(StrEnum):
    NONE = "none"
    DAILY_LIMIT = "daily_limit"
    TIMER_EXPIRED = "timer_expired"
    OUTSIDE_ALLOWED_PERIOD = "outside_allowed_period"


@dataclass(slots=True)
class GameIdentity:
    app_id: str | None
    name: str
    source: str
    pids: tuple[int, ...] = ()
    confidence: float = 1.0
    instance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["pids"] = list(self.pids)
        return result


@dataclass(slots=True)
class DomainEvent:
    kind: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "occurred_at": self.occurred_at.isoformat(),
            "severity": self.severity,
            "payload": self.payload,
        }


@dataclass(slots=True)
class TimerSnapshot:
    state: TimerState = TimerState.IDLE
    configured_seconds: int = 0
    remaining_seconds: float = 0.0
    action: str = "inherit"
    generation: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["state"] = self.state.value
        result["remaining_seconds"] = max(0, int(round(self.remaining_seconds)))
        return result
