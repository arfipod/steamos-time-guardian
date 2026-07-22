# Troubleshooting

## First response

```bash
./scripts/status.sh
./scripts/diagnose.sh
journalctl --user -u steamos-time-guardian.service --since -30m --no-pager
./scripts/diagnose.sh --bundle "$HOME/stg-support.tar.gz"
```

Inspect a support archive before sharing it. It excludes session history but can reveal software versions and policy choices.

## Service does not start

```bash
systemctl --user daemon-reload
systemctl --user reset-failed steamos-time-guardian.service
systemctl --user restart steamos-time-guardian.service
systemctl --user status steamos-time-guardian.service
```

Common causes: Python older than 3.11, bad copied files, unsupported config, XDG permissions, or stale socket. Do not delete the database. Stop the service and remove only runtime files if diagnostics prove no live process.

## Cannot connect to daemon

```bash
echo "$XDG_RUNTIME_DIR"
ls -la "$XDG_RUNTIME_DIR/steamos-time-guardian"
systemctl --user is-active steamos-time-guardian.service
```

CLI and daemon must use the same account/XDG session. A shell outside the graphical session can lack `XDG_RUNTIME_DIR`; do not loosen socket permissions.

## Corrupt configuration

The daemon quarantines invalid config as `config.corrupt-*.json` and installs defaults. Repair a copy and apply small validated patches. Unknown keys are intentionally rejected.

## Database health error

```bash
systemctl --user stop steamos-time-guardian.service
cp -a ~/.local/share/steamos-time-guardian "$HOME/stg-data-backup-$(date +%s)"
```

Do not run ad-hoc repair on the only copy. A fresh database loses history and requires approval.

## Game is not detected

Check Decky heartbeat/current app, Steam log path/recent entries, same-user App ID environment, and ignored IDs/names.

```bash
ls -l ~/.local/share/Steam/logs/gameprocess_log.txt ~/.steam/steam/logs/gameprocess_log.txt 2>/dev/null
journalctl --user -u steamos-time-guardian.service | grep -E 'detector|game\.'
```

For non-Steam/App ID zero and emulators, capture the exact launcher/log fixture during hardware validation. Do not add broad executable-name matching.

## False detection

Add a precise App ID to `detector.ignored_app_ids` or narrowly justified name, then restart if recommended. Capture source/confidence before filtering.

## Notifications absent

```bash
command -v notify-send
notify-send 'SteamOS Time Guardian test' 'Desktop notification path'
```

Game Mode requires loaded Decky; Desktop notifications are not guaranteed to overlay games. Events are still recorded.

## Decky panel missing

Decky is optional. Confirm daemon from Desktop Mode first. Decky's documentation notes it can disappear after SteamOS updates; use its official repair flow rather than changing the SteamOS root. Reinstall/reload this plugin and preserve daemon data.

## Controlled close did not work

Safe failure is preferred. Verify level/grace, plugin heartbeat/result, nonzero matching App ID, same-user candidate PIDs, and fallback setting. Keep force kill disabled. Never substitute `killall`, `pkill`, or name-based termination.

## Unexpected time after suspend/clock change

Inspect suspend/resume/inferred-gap/UTC-offset/daily-reset events. Report exact wall times, time zone, SteamOS version, and whether NTP/manual clock change occurred.

## Recovery sequence

1. Stop/disable user service.
2. Use Desktop/SSH; preserve recovery paths.
3. Export/copy config/data.
4. Uninstall program files without purge.
5. Reinstall level 0 without Decky.
6. Validate diagnostics/simulation.
7. Reintroduce Decky/enforcement only after root cause is understood.
