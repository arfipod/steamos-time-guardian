"""Daily accounting windows and weekly limit calculations."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_hhmm(value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid HH:MM value: {value!r}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid HH:MM value: {value!r}")
    return time(hour=hour, minute=minute)


def system_timezone() -> tzinfo:
    """Resolve the local IANA zone when Linux exposes it, with a safe offset fallback.

    ``datetime.now().astimezone().tzinfo`` can be only a fixed-offset object on some systems,
    which would lose future daylight-saving transitions. SteamOS normally links
    ``/etc/localtime`` into ``/usr/share/zoneinfo``, so prefer that stable identifier.
    """
    candidates: list[str] = []
    if tz_env := os.environ.get("TZ"):
        candidates.append(tz_env.removeprefix(":"))
    try:
        resolved = Path("/etc/localtime").resolve()
        marker = "/usr/share/zoneinfo/"
        if marker in str(resolved):
            candidates.append(str(resolved).split(marker, 1)[1])
    except OSError:
        pass
    try:
        timezone_file = Path("/etc/timezone")
        if timezone_file.is_file():
            candidates.append(timezone_file.read_text(encoding="utf-8").strip())
    except OSError:
        pass
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except ZoneInfoNotFoundError:
            continue
    return datetime.now().astimezone().tzinfo or UTC


def resolve_timezone(name: str) -> tzinfo:
    if name == "system":
        return system_timezone()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc


def local_datetime(now_utc: datetime, timezone_name: str) -> datetime:
    aware = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)
    return aware.astimezone(resolve_timezone(timezone_name))


def accounting_day(now_utc: datetime, reset_at: str, timezone_name: str = "system") -> date:
    local = local_datetime(now_utc, timezone_name)
    reset = parse_hhmm(reset_at)
    day = local.date()
    if local.time().replace(tzinfo=None) < reset:
        day -= timedelta(days=1)
    return day


def accounting_day_key(now_utc: datetime, reset_at: str, timezone_name: str = "system") -> str:
    return accounting_day(now_utc, reset_at, timezone_name).isoformat()


def accounting_day_start(day: date, reset_at: str, timezone_name: str = "system") -> datetime:
    """Return the UTC instant at which an accounting day starts.

    For a reset clock that falls in a daylight-saving gap, the round-trip through UTC moves
    the value to the first representable local instant after the gap. For an ambiguous clock
    value, ``fold=0`` deliberately chooses the first occurrence.
    """
    zone = resolve_timezone(timezone_name)
    reset = parse_hhmm(reset_at)
    local = datetime.combine(day, reset, tzinfo=zone).replace(fold=0)
    utc_value = local.astimezone(UTC)
    round_trip = utc_value.astimezone(zone)
    if round_trip.date() != day or round_trip.time().replace(tzinfo=None) != reset:
        return round_trip.astimezone(UTC)
    return utc_value


def limit_for_day(config: dict, day: date) -> int | None:
    weekday = WEEKDAYS[day.weekday()]
    entry = config["daily_limits"]["weekly"][weekday]
    if entry.get("unlimited", False):
        return None
    return int(entry["minutes"]) * 60


def seconds_until_reset(now_utc: datetime, reset_at: str, timezone_name: str = "system") -> int:
    aware = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)
    current_day = accounting_day(aware, reset_at, timezone_name)
    candidate = accounting_day_start(current_day + timedelta(days=1), reset_at, timezone_name)
    return max(0, int((candidate - aware.astimezone(UTC)).total_seconds()))


def within_allowed_period(config: dict, now_utc: datetime) -> bool:
    periods = config["daily_limits"].get("allowed_periods", [])
    if not periods:
        return True
    local = local_datetime(now_utc, config["daily_limits"]["timezone"])
    weekday_index = local.weekday()
    weekday = WEEKDAYS[weekday_index]
    previous_weekday = WEEKDAYS[(weekday_index - 1) % len(WEEKDAYS)]
    current = local.time().replace(second=0, microsecond=0)
    for period in periods:
        days = period.get("days", WEEKDAYS)
        start = parse_hhmm(period["start"])
        end = parse_hhmm(period["end"])
        if start <= end:
            if weekday in days and start <= current < end:
                return True
        else:
            # ``days`` identifies the day on which an overnight interval starts. Therefore
            # Monday 22:00–02:00 also permits Tuesday 00:00–01:59 without requiring Tuesday.
            if weekday in days and current >= start:
                return True
            if previous_weekday in days and current < end:
                return True
    return False
