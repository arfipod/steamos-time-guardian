"""Desktop notification adapter; Game Mode notifications are emitted to Decky subscribers."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass

LOGGER = logging.getLogger("stg.notifications")


@dataclass(slots=True)
class Notification:
    title: str
    body: str
    urgency: str = "normal"
    persistent: bool = False

    def to_event_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "urgency": self.urgency,
            "persistent": self.persistent,
        }


class NativeNotifier:
    """Calls notify-send without a shell. Failure is non-fatal and logged once per call."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.command = shutil.which("notify-send")

    @property
    def available(self) -> bool:
        return bool(self.command)

    async def send(self, notification: Notification) -> bool:
        if not self.enabled or not self.command:
            return False
        title = notification.title.replace("\x00", "")[:120]
        body = notification.body.replace("\x00", "")[:500]
        urgency = notification.urgency if notification.urgency in {"low", "normal", "critical"} else "normal"
        timeout = "0" if notification.persistent else "7000"
        try:
            process = await asyncio.create_subprocess_exec(
                self.command,
                "--app-name=SteamOS Time Guardian",
                f"--urgency={urgency}",
                f"--expire-time={timeout}",
                title,
                body,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
            if process.returncode != 0:
                LOGGER.warning("notify-send failed: %s", stderr.decode(errors="replace")[:300])
                return False
            return True
        except (OSError, TimeoutError) as exc:
            LOGGER.warning("native notification failed: %s", exc)
            return False
