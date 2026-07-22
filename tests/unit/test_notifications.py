from __future__ import annotations

import unittest

from stg.notifications import NativeNotifier, Notification


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_notifier_is_safe(self):
        notifier = NativeNotifier(enabled=False)
        self.assertFalse(await notifier.send(Notification("Title", "Body")))

    def test_payload_is_serializable(self):
        payload = Notification("Title", "Body", "critical", True).to_event_payload()
        self.assertTrue(payload["persistent"])
        self.assertEqual(payload["urgency"], "critical")
