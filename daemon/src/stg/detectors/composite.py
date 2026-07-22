"""Arbitrates multiple detectors while preferring event-oriented sources."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterable

from .base import Detector, DetectorEvent, DetectorEventType

_SOURCE_PRIORITY = {"decky": 100, "simulation": 95, "steam_log": 80, "procfs": 50}


class CompositeDetector:
    def __init__(self, detectors: Iterable[Detector]):
        self.detectors = list(detectors)
        self._tasks: list[asyncio.Task[None]] = []
        self._stopped = False
        self._current_source_priority = 0
        self._current_key: tuple[str | None, str] | None = None

    async def run(self, output: asyncio.Queue[DetectorEvent]) -> None:
        child_output: asyncio.Queue[DetectorEvent] = asyncio.Queue()
        self._tasks = [asyncio.create_task(detector.run(child_output)) for detector in self.detectors]
        try:
            while not self._stopped:
                event = await child_output.get()
                if event.type == DetectorEventType.ERROR:
                    await output.put(event)
                    continue
                priority = _SOURCE_PRIORITY.get(event.game.source if event.game else "", 0)
                if event.type in {DetectorEventType.STARTED, DetectorEventType.CHANGED}:
                    if priority >= self._current_source_priority:
                        self._current_source_priority = priority
                        self._current_key = self._key(event)
                        await output.put(event)
                elif event.type == DetectorEventType.STOPPED:
                    event_key = self._key(event)
                    if priority >= self._current_source_priority and (
                        self._current_key is None or event_key == self._current_key
                    ):
                        self._current_source_priority = 0
                        self._current_key = None
                        await output.put(event)
                else:
                    await output.put(event)
        finally:
            for task in self._tasks:
                task.cancel()
            for task in self._tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def stop(self) -> None:
        self._stopped = True
        for detector in self.detectors:
            await detector.stop()

    @staticmethod
    def _key(event: DetectorEvent) -> tuple[str | None, str] | None:
        if not event.game:
            return None
        return event.game.app_id, event.game.name.casefold()
