# Configuration, data, and migrations

## Locations

| Purpose | Default path | Mode |
|---|---|---:|
| Configuration | `~/.config/steamos-time-guardian/config.json` | `0600` |
| Database | `~/.local/share/steamos-time-guardian/guardian.db` | user-only directory |
| Structured log | `~/.local/state/steamos-time-guardian/guardian.jsonl` | user-only directory |
| Support bundles | `~/.local/state/steamos-time-guardian/support/` | user-only directory |
| RPC socket | `$XDG_RUNTIME_DIR/steamos-time-guardian/control.sock` | `0600` |

A development fallback uses `/tmp/steamos-time-guardian-$UID` when `XDG_RUNTIME_DIR` is absent.

## Schema and defaults

Configuration schema version is **2**. Canonical defaults are in `daemon/src/stg/config.py`, the example in `config/config.example.json`, and the JSON Schema in `config/schema.json`. They must remain synchronized.

Unknown keys are rejected. Updates are deep-merged, validated, written to a temporary file, `fsync`ed, and atomically renamed. A corrupt file moves to `config.corrupt-<UTC>.json`, safe defaults are regenerated, and recovery appears in diagnostics.

### Daily limits

Every weekday must exist. `minutes` is 0–1440. `unlimited=true` suppresses the base limit for that accounting day. `timezone` is `system`, `UTC`, or an available IANA zone. `reset_at` is local `HH:MM`.

Optional allowed periods:

```json
{
  "daily_limits": {
    "allowed_periods": [
      {"start": "17:00", "end": "21:00", "days": ["monday", "tuesday"]},
      {"start": "18:00", "end": "00:30", "days": ["friday"]}
    ]
  }
}
```

An empty list permits all times. Cross-midnight periods are supported.
For a cross-midnight period, `days` names the day on which the period starts: a Friday
`18:00`–`00:30` window therefore remains valid through Saturday 00:30.

### Warnings

`threshold_minutes` is normalized to unique descending positive integers. Default: `[30, 15, 5, 1]`. `notify_at_exhaustion` adds threshold zero. `native_desktop_notifications` controls `notify-send`.

### Timer

`count_only_while_playing=true` freezes a running manual timer without detected gameplay. `default_action` is `inherit`, `notify_only`, `soft`, `close`, or `block`.

### Restriction

- `level`: 0–3.
- `grace_seconds`: voluntary save/quit time.
- `close_timeout_seconds`: wait before optional force action.
- `force_kill_enabled`: false by default.
- `launch_grace_seconds`: shorter level-3 launch delay.
- `safe_process_fallback`: after the Steam close request and timeout, allow a verified
  same-user `SIGTERM` fallback. A Decky result event is diagnostic in this MVP; actual game
  disappearance cancels the flow. The same timeout is used again after `SIGTERM` before an
  optional, explicitly enabled `SIGKILL` attempt.

### Detector

`mode` is `auto`, `steam_log`, `procfs`, or `disabled`. `steam_log_path` may be `auto` or an
explicit readable file. `procfs_fallback_interval_seconds` is 5–300, default 15.
`decky_signal_ttl_seconds` controls high-confidence plugin freshness. Ignored IDs/names reduce
UI false positives.

### History and logging

History retention is 1–3650 days, default 90. Checkpoint is 5–600 seconds, default 30.
`history.backup_count` keeps up to 0–20 automatic SQLite snapshots before a schema migration;
default 3. Logs support `DEBUG`, `INFO`, `WARNING`, and `ERROR`, with size-based rotation.

## Changing configuration

```bash
steamos-time-guardian config show
steamos-time-guardian config patch '{"daily_limits":{"reset_at":"04:00"}}'
steamos-time-guardian config patch @my-patch.json
```

Detector, logging, and simulation patches return `restart_recommended`; apply with:

```bash
systemctl --user restart steamos-time-guardian.service
```

## Exceptional time

```bash
steamos-time-guardian bonus 30m --reason "One-time allowance"
steamos-time-guardian bonus -15m --reason "Correction"
```

Adjustments are history rows associated with the accounting day. Positive time clears relevant warning marks.

History deletion is intentionally rejected while a game session is open. Stop/close the game
first, then use the explicit `PURGE_HISTORY` confirmation exposed by the CLI/API.

## Database migrations and recovery

`PRAGMA user_version` tracks schema version. Migrations are ordered functions in `storage.py`
and tested from older fixture schemas. Before upgrading an existing older schema, the daemon
creates a SQLite-consistent `guardian.pre-v*-migration-*.db` snapshot and prunes it according to
`history.backup_count`. Never edit live SQLite while the service is running.

```bash
systemctl --user stop steamos-time-guardian.service
cp -a ~/.local/share/steamos-time-guardian/guardian.db{,.backup}
```

Do not assume the `sqlite3` CLI exists on SteamOS; built-in diagnostics use Python's SQLite module.

## Backups and exports

For a complete backup, stop the service and copy config/data directories. The support bundle excludes history. JSON export includes metadata and arrays of sessions/adjustments/events; CSV export contains session fields. Export never uploads data.
