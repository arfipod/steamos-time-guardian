"""Detector interfaces and events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from stg.models import GameIdentity


class DetectorEventType(StrEnum):
    STARTED = "started"
    STOPPED = "stopped"
    CHANGED = "changed"
    SUSPEND = "suspend"
    RESUME = "resume"
    ERROR = "error"


@dataclass(slots=True)
class DetectorEvent:
    type: DetectorEventType
    game: GameIdentity | None = None
    reason: str | None = None


class Detector(Protocol):
    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None: ...

    async def stop(self) -> None: ...
