"""Configuration defaults, validation, atomic persistence, and migrations."""

from __future__ import annotations

import copy
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schedule import WEEKDAYS, parse_hhmm, resolve_timezone

CONFIG_SCHEMA_VERSION = 2

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "language": "en",
    "daily_limits": {
        "enabled": True,
        "reset_at": "00:00",
        "timezone": "system",
        "weekly": {
            day: {"minutes": 120, "unlimited": False} for day in WEEKDAYS
        },
        "allowed_periods": [],
    },
    "warnings": {
        "threshold_minutes": [30, 15, 5, 1],
        "notify_at_exhaustion": True,
        "native_desktop_notifications": True,
    },
    "timer": {
        "count_only_while_playing": True,
        "default_minutes": 30,
        "default_action": "inherit",
    },
    "restriction": {
        "level": 0,
        "grace_seconds": 60,
        "close_timeout_seconds": 20,
        "force_kill_enabled": False,
        "launch_grace_seconds": 5,
        "safe_process_fallback": True,
    },
    "detector": {
        "mode": "auto",
        "steam_log_path": "auto",
        "procfs_fallback_interval_seconds": 15,
        "decky_signal_ttl_seconds": 20,
        "ignored_app_ids": ["769"],
        "ignored_names": ["Steam", "gamescope", "steamwebhelper"],
    },
    "history": {
        "retention_days": 90,
        "checkpoint_seconds": 30,
        "backup_count": 3,
    },
    "logging": {"level": "INFO", "max_bytes": 2_000_000, "backup_count": 3},
    "simulation": {"enabled": False},
}


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


def _merge(default: Any, supplied: Any) -> Any:
    if isinstance(default, dict) and isinstance(supplied, dict):
        result = copy.deepcopy(default)
        for key, value in supplied.items():
            result[key] = _merge(default[key], value) if key in default else copy.deepcopy(value)
        return result
    return copy.deepcopy(supplied)


def _reject_unknown_keys(supplied: Any, template: Any, path: str = "") -> None:
    """Reject misspelled or unsupported settings before defaults are merged.

    Lists are validated by their domain-specific validators below. This keeps configuration
    updates strict without making partial nested patches impossible.
    """
    if not isinstance(supplied, dict) or not isinstance(template, dict):
        return
    for key, value in supplied.items():
        dotted = f"{path}.{key}" if path else key
        if key not in template:
            raise ConfigError(f"unknown configuration key: {dotted}")
        _reject_unknown_keys(value, template[key], dotted)


def migrate_config(raw: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(raw)
    raw_version = data.get("schema_version", 1)
    if isinstance(raw_version, bool):
        raise ConfigError("schema_version must be an integer")
    try:
        version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise ConfigError("schema_version must be an integer") from exc
    if version > CONFIG_SCHEMA_VERSION:
        raise ConfigError(
            f"configuration schema {version} is newer than supported {CONFIG_SCHEMA_VERSION}"
        )
    _reject_unknown_keys(data, DEFAULT_CONFIG)
    if version < 2:
        data.setdefault("restriction", {}).setdefault("launch_grace_seconds", 5)
        data.setdefault("detector", {}).setdefault("decky_signal_ttl_seconds", 20)
        data["schema_version"] = 2
    return _merge(DEFAULT_CONFIG, data)


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    cfg = migrate_config(config)
    errors: list[str] = []
    if cfg.get("schema_version") != CONFIG_SCHEMA_VERSION:
        errors.append("schema_version must be 2")
    if cfg.get("language") not in {"en", "es"}:
        errors.append("language must be en or es")
    if not isinstance(cfg["daily_limits"].get("enabled"), bool):
        errors.append("daily_limits.enabled must be boolean")
    try:
        parse_hhmm(cfg["daily_limits"]["reset_at"])
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    try:
        resolve_timezone(cfg["daily_limits"]["timezone"])
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    weekly = cfg["daily_limits"].get("weekly", {})
    for day in WEEKDAYS:
        entry = weekly.get(day)
        if not isinstance(entry, dict):
            errors.append(f"missing weekly limit for {day}")
            continue
        minutes = entry.get("minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 0 <= minutes <= 1440:
            errors.append(f"{day}.minutes must be an integer from 0 to 1440")
        if not isinstance(entry.get("unlimited"), bool):
            errors.append(f"{day}.unlimited must be boolean")
    thresholds = cfg["warnings"].get("threshold_minutes", [])
    if not isinstance(thresholds, list) or any(
        not isinstance(item, int) or isinstance(item, bool) or item <= 0 or item > 1440
        for item in thresholds
    ):
        errors.append("warnings.threshold_minutes must contain positive integer minutes")
    else:
        cfg["warnings"]["threshold_minutes"] = sorted(set(thresholds), reverse=True)
    for key in ("notify_at_exhaustion", "native_desktop_notifications"):
        if not isinstance(cfg["warnings"].get(key), bool):
            errors.append(f"warnings.{key} must be boolean")
    if not isinstance(cfg["timer"].get("count_only_while_playing"), bool):
        errors.append("timer.count_only_while_playing must be boolean")
    default_minutes = cfg["timer"].get("default_minutes")
    if (
        not isinstance(default_minutes, int)
        or isinstance(default_minutes, bool)
        or not 1 <= default_minutes <= 1440
    ):
        errors.append("timer.default_minutes must be an integer from 1 to 1440")
    if cfg["timer"].get("default_action") not in {
        "inherit",
        "notify_only",
        "soft",
        "close",
        "block",
    }:
        errors.append("timer.default_action is unsupported")
    level = cfg["restriction"].get("level")
    if not isinstance(level, int) or isinstance(level, bool) or level not in range(4):
        errors.append("restriction.level must be 0, 1, 2, or 3")
    for key in ("grace_seconds", "close_timeout_seconds", "launch_grace_seconds"):
        value = cfg["restriction"].get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3600:
            errors.append(f"restriction.{key} must be an integer from 0 to 3600")
    for key in ("force_kill_enabled", "safe_process_fallback"):
        if not isinstance(cfg["restriction"].get(key), bool):
            errors.append(f"restriction.{key} must be boolean")
    if cfg["detector"].get("mode") not in {"auto", "steam_log", "procfs", "disabled"}:
        errors.append("detector.mode must be auto, steam_log, procfs, or disabled")
    steam_log_path = cfg["detector"].get("steam_log_path")
    if not isinstance(steam_log_path, str) or not steam_log_path.strip() or "\x00" in steam_log_path:
        errors.append("detector.steam_log_path must be a non-empty path or auto")
    interval = cfg["detector"].get("procfs_fallback_interval_seconds")
    if not isinstance(interval, int) or isinstance(interval, bool) or not 5 <= interval <= 300:
        errors.append("detector.procfs_fallback_interval_seconds must be 5..300")
    signal_ttl = cfg["detector"].get("decky_signal_ttl_seconds")
    if (
        not isinstance(signal_ttl, int)
        or isinstance(signal_ttl, bool)
        or not 5 <= signal_ttl <= 300
    ):
        errors.append("detector.decky_signal_ttl_seconds must be 5..300")
    ignored_ids = cfg["detector"].get("ignored_app_ids")
    if (
        not isinstance(ignored_ids, list)
        or any(not isinstance(item, str) or not item.isdigit() for item in ignored_ids)
    ):
        errors.append("detector.ignored_app_ids must contain decimal strings")
    else:
        cfg["detector"]["ignored_app_ids"] = list(dict.fromkeys(ignored_ids))
    ignored_names = cfg["detector"].get("ignored_names")
    if (
        not isinstance(ignored_names, list)
        or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in ignored_names)
    ):
        errors.append("detector.ignored_names must contain non-empty strings up to 200 characters")
    else:
        cfg["detector"]["ignored_names"] = list(dict.fromkeys(item.strip() for item in ignored_names))
    retention = cfg["history"].get("retention_days")
    if not isinstance(retention, int) or isinstance(retention, bool) or not 1 <= retention <= 3650:
        errors.append("history.retention_days must be 1..3650")
    checkpoint = cfg["history"].get("checkpoint_seconds")
    if not isinstance(checkpoint, int) or isinstance(checkpoint, bool) or not 5 <= checkpoint <= 600:
        errors.append("history.checkpoint_seconds must be 5..600")
    history_backups = cfg["history"].get("backup_count")
    if (
        not isinstance(history_backups, int)
        or isinstance(history_backups, bool)
        or not 0 <= history_backups <= 20
    ):
        errors.append("history.backup_count must be an integer from 0 to 20")
    if cfg["logging"].get("level") not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        errors.append("logging.level must be DEBUG, INFO, WARNING, or ERROR")
    max_bytes = cfg["logging"].get("max_bytes")
    if (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or not 100_000 <= max_bytes <= 100_000_000
    ):
        errors.append("logging.max_bytes must be an integer from 100000 to 100000000")
    log_backups = cfg["logging"].get("backup_count")
    if (
        not isinstance(log_backups, int)
        or isinstance(log_backups, bool)
        or not 0 <= log_backups <= 20
    ):
        errors.append("logging.backup_count must be an integer from 0 to 20")
    if not isinstance(cfg["simulation"].get("enabled"), bool):
        errors.append("simulation.enabled must be boolean")
    periods = cfg["daily_limits"].get("allowed_periods", [])
    if not isinstance(periods, list):
        errors.append("daily_limits.allowed_periods must be a list")
    else:
        for index, period in enumerate(periods):
            try:
                if not isinstance(period, dict):
                    raise TypeError("period must be an object")
                unknown = set(period) - {"start", "end", "days"}
                if unknown:
                    raise ValueError(f"unknown keys: {', '.join(sorted(unknown))}")
                start = parse_hhmm(period["start"])
                end = parse_hhmm(period["end"])
                if start == end:
                    raise ValueError("start and end must differ")
                days = period.get("days", WEEKDAYS)
                if not isinstance(days, list) or any(not isinstance(day, str) for day in days):
                    raise TypeError("days must be a list of weekday names")
                if any(day not in WEEKDAYS for day in days):
                    raise ValueError("unknown weekday")
                if len(days) != len(set(days)):
                    raise ValueError("duplicate weekday")
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"allowed_periods[{index}]: {exc}")
    if errors:
        raise ConfigError("; ".join(errors))
    return cfg


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self.last_recovery: str | None = None

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            config = validate_config(DEFAULT_CONFIG)
            self.save(config)
            return config
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ConfigError("configuration root must be an object")
            config = validate_config(raw)
            if config != raw:
                self.save(config)
            return config
        except (OSError, json.JSONDecodeError, ConfigError) as exc:
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            quarantine = self.path.with_name(f"config.corrupt-{timestamp}.json")
            try:
                shutil.move(self.path, quarantine)
            except OSError:
                pass
            self.last_recovery = f"invalid configuration quarantined: {exc}"
            config = validate_config(DEFAULT_CONFIG)
            self.save(config)
            return config

    def save(self, config: dict[str, Any]) -> dict[str, Any]:
        validated = validate_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        payload = json.dumps(validated, indent=2, sort_keys=True) + "\n"
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        try:
            directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return validated

    def update(self, patch: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        merged = _merge(current, patch)
        return self.save(merged)
