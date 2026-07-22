from __future__ import annotations

import copy
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from stg.clock import FakeClock
from stg.config import DEFAULT_CONFIG, validate_config
from stg.engine import GuardianEngine
from stg.paths import AppPaths
from stg.storage import Storage


def test_config(**overrides):
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["daily_limits"]["timezone"] = "UTC"
    config["warnings"]["native_desktop_notifications"] = False
    config["history"]["checkpoint_seconds"] = 5
    for section, values in overrides.items():
        if isinstance(values, dict) and isinstance(config.get(section), dict):
            config[section].update(values)
        else:
            config[section] = values
    return validate_config(config)


test_config.__test__ = False


class EngineFixture:
    def __init__(self, when: datetime | None = None, config=None):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = Storage(self.root / "guardian.db")
        self.storage.open()
        self.clock = FakeClock(when or datetime(2026, 7, 20, 12, 0, tzinfo=UTC))
        self.config = config or test_config()
        self.engine = GuardianEngine(self.storage, self.config, self.clock)

    def close(self):
        self.storage.close()
        self.temp.cleanup()


def temporary_paths(root: Path) -> AppPaths:
    return AppPaths(
        config_dir=root / "config",
        data_dir=root / "data",
        state_dir=root / "state",
        runtime_dir=root / "runtime",
    )
