"""Clock abstractions for deterministic timekeeping tests."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


@dataclass(slots=True)
class FakeClock:
    current_utc: datetime
    current_monotonic: float = 0.0

    def __post_init__(self) -> None:
        if self.current_utc.tzinfo is None:
            self.current_utc = self.current_utc.replace(tzinfo=UTC)
        self.current_utc = self.current_utc.astimezone(UTC)

    def now_utc(self) -> datetime:
        return self.current_utc

    def monotonic(self) -> float:
        return self.current_monotonic

    def advance(self, seconds: float, *, wall_seconds: float | None = None) -> None:
        self.current_monotonic += seconds
        self.current_utc += timedelta(seconds=seconds if wall_seconds is None else wall_seconds)

    def jump_wall(self, seconds: float) -> None:
        self.current_utc += timedelta(seconds=seconds)
