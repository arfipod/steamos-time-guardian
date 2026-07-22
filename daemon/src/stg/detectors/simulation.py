"""Deterministic detector used on ordinary Linux systems and in tests."""

from __future__ import annotations

import asyncio

from .base import DetectorEvent


class SimulationDetector:
    def __init__(self):
        self._queue: asyncio.Queue[DetectorEvent | None] = asyncio.Queue()
        self._stopped = False

    async def emit(self, event: DetectorEvent) -> None:
        await self._queue.put(event)

    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None:
        while not self._stopped:
            item = await self._queue.get()
            if item is None:
                break
            await output.put(item)

    async def stop(self) -> None:
        self._stopped = True
        await self._queue.put(None)
