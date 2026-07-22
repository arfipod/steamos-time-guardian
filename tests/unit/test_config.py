from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stg.config import CONFIG_SCHEMA_VERSION, ConfigError, ConfigStore, DEFAULT_CONFIG, migrate_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_defaults_validate(self):
        config = validate_config(DEFAULT_CONFIG)
        self.assertEqual(config["schema_version"], CONFIG_SCHEMA_VERSION)
        self.assertEqual(config["warnings"]["threshold_minutes"], [30, 15, 5, 1])

    def test_v1_migration_adds_new_keys(self):
        old = json.loads(json.dumps(DEFAULT_CONFIG))
        old["schema_version"] = 1
        del old["restriction"]["launch_grace_seconds"]
        del old["detector"]["decky_signal_ttl_seconds"]
        migrated = migrate_config(old)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["restriction"]["launch_grace_seconds"], 5)


    def test_unknown_key_rejected(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["restriction"]["grace_secondz"] = 10
        with self.assertRaisesRegex(ConfigError, "unknown configuration key"):
            validate_config(bad)

    def test_unknown_allowed_period_key_rejected(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["daily_limits"]["allowed_periods"] = [
            {"start": "18:00", "end": "20:00", "days": ["monday"], "typo": True}
        ]
        with self.assertRaisesRegex(ConfigError, "unknown keys"):
            validate_config(bad)

    def test_invalid_level_rejected(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["restriction"]["level"] = 9
        with self.assertRaises(ConfigError):
            validate_config(bad)

    def test_invalid_scalar_types_are_rejected(self):
        cases = (
            ("daily_limits", "enabled", "yes"),
            ("warnings", "notify_at_exhaustion", 1),
            ("timer", "default_minutes", True),
            ("restriction", "force_kill_enabled", "false"),
            ("detector", "decky_signal_ttl_seconds", 1),
            ("logging", "level", "TRACE"),
            ("simulation", "enabled", 0),
        )
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                bad = json.loads(json.dumps(DEFAULT_CONFIG))
                bad[section][key] = value
                with self.assertRaises(ConfigError):
                    validate_config(bad)

    def test_zero_length_allowed_period_is_rejected(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["daily_limits"]["allowed_periods"] = [
            {"start": "18:00", "end": "18:00", "days": ["monday"]}
        ]
        with self.assertRaisesRegex(ConfigError, "start and end must differ"):
            validate_config(bad)

    def test_corrupt_file_is_quarantined_and_defaults_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{broken", encoding="utf-8")
            store = ConfigStore(path)
            config = store.load()
            self.assertEqual(config["schema_version"], 2)
            self.assertIsNotNone(store.last_recovery)
            self.assertTrue(list(path.parent.glob("config.corrupt-*.json")))
            self.assertEqual(json.loads(path.read_text())["schema_version"], 2)

    def test_non_numeric_schema_version_is_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"schema_version":"broken"}', encoding="utf-8")
            store = ConfigStore(path)
            config = store.load()
            self.assertEqual(config["schema_version"], 2)
            self.assertIsNotNone(store.last_recovery)

    def test_atomic_update_preserves_nested_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            current = store.load()
            updated = store.update({"restriction": {"level": 2}}, current)
            self.assertEqual(updated["restriction"]["level"], 2)
            self.assertEqual(updated["restriction"]["grace_seconds"], 60)
