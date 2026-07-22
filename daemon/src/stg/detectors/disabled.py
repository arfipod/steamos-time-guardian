"""No-op detector used when automatic game detection is explicitly disabled."""

from __future__ import annotations

import asyncio

from .base import DetectorEvent


class DisabledDetector:
    """Wait without polling until the service asks the detector to stop."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()

    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None:
        del output
        await self._stop_event.wait()

    async def stop(self) -> None:
        self._stop_event.set()
