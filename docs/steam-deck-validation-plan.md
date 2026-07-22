# Steam Deck validation plan over SSH

**Status:** procedure only; not executed. Start with restriction level 0 and force kill disabled. Every write, restart, close, or privilege-requiring action needs the owner's approval. Record a dated transcript without credentials or private history.

## Decisions to confirm before connecting

- Target device/account, stable channel, backup state, and whether updating first is permitted.
- Whether Decky Loader is installed and plugin installation is approved.
- Disposable/non-critical test games; later include non-Steam/emulator if approved.
- Weekly allowance, reset time, time zone, allowed periods, retention.
- Maximum restriction level; default 0, level 2 only after separate approval.
- Whether verified same-user `SIGTERM` fallback may be tested; keep `SIGKILL` disabled.
- Permission to restart only this user service and, separately, to reload/restart Steam through its UI.
- Recovery route: physical access/Desktop Mode plus copied uninstall command.

## 1. Read-only inventory

```bash
id
printf 'HOME=%s\nXDG_RUNTIME_DIR=%s\n' "$HOME" "${XDG_RUNTIME_DIR:-}"
cat /etc/os-release
uname -a
python3 --version
systemctl --user --version
systemctl --user show-environment | sed -n '1,80p'
df -h "$HOME"
```

Expected: expected unprivileged user/device, writable home, graphical-session runtime directory, Python >=3.11, user systemd. Stop on mismatch.

## 2. Confirm SteamOS stable version/channel

Visually confirm Settings → System → update channel **Stable**. Preserve output:

```bash
grep -E '^(NAME|VERSION|VERSION_ID|BUILD_ID|VARIANT_ID)=' /etc/os-release
```

Research baseline: SteamOS 3.8.x, with 3.8.16 the newest stable notice found on 2026-07-22. If newer, repeat SteamOS/Decky/API research before installation. Do not force an update without approval.

## 3. Inspect Decky without changes

```bash
ls -ld "$HOME/homebrew" "$HOME/homebrew/plugins" 2>/dev/null || true
pgrep -a -f 'PluginLoader|decky' || true
systemctl status plugin_loader.service --no-pager 2>/dev/null || true
find "$HOME/homebrew" -maxdepth 2 -type f -name plugin.json -print 2>/dev/null | head
```

Record Decky version from Game Mode settings. Do not install/upgrade it yet.

## 4. Transfer, verify, extract under home

From host:

```bash
scp steamos-time-guardian.zip steamos-time-guardian.zip.sha256 deck@DEVICE:~/
```

On Deck:

```bash
cd "$HOME"
sha256sum -c steamos-time-guardian.zip.sha256
python3 -m zipfile -t steamos-time-guardian.zip
mkdir -p "$HOME/stg-validation-src"
python3 -m zipfile -e steamos-time-guardian.zip "$HOME/stg-validation-src"
cd "$HOME/stg-validation-src/steamos-time-guardian"
```

If the extraction target already exists, stop and ask before removal. Expected: checksum and archive test pass.

## 5. Pre-install validation

```bash
./scripts/install-user.sh --dry-run
./scripts/build.sh --python-only
./scripts/test.sh --python-only
./scripts/smoke-test.sh
```

If Node/TypeScript are absent, do not install system packages; validate committed Decky output on host. Expected: tests/smoke pass.

Review for root mutation:

```bash
grep -RInE 'steamos-readonly|sudo +pacman' scripts systemd packaging || true
```

Expected: no executable root mutation path.

## 6. Install daemon without Decky, level 0

```bash
./scripts/install-user.sh
steamos-time-guardian config patch '{"restriction":{"level":0,"force_kill_enabled":false}}'
systemctl --user restart steamos-time-guardian.service
```

Expected: no sudo prompt/root change; active user service.

## 7. Service and IPC health

```bash
systemctl --user status steamos-time-guardian.service --no-pager
systemctl --user show steamos-time-guardian.service -p MainPID -p MemoryCurrent -p CPUUsageNSec
ls -ld "$XDG_RUNTIME_DIR/steamos-time-guardian"
ls -l "$XDG_RUNTIME_DIR/steamos-time-guardian/control.sock"
steamos-time-guardian --json status | python3 -m json.tool
steamos-time-guardian --json diagnose | python3 -m json.tool
```

Expected: directory `0700`, socket `srw-------`, DB quick check `ok`, schema 2, level 0.

## 8. Desktop interface

Switch to Desktop Mode and launch “SteamOS Time Guardian”, or run:

```bash
steamos-time-guardian tui
```

Expected: Summary, Timer, Daily Limit, Weekly, History, Settings, Diagnostics; readable text and usable controls. Validate D-pad/sticks/touch on-device. No permanent overlay.

## 9. Isolated simulator on device

Stop production service and use separate XDG paths only after approval:

```bash
systemctl --user stop steamos-time-guardian.service
work=$(mktemp -d "$HOME/stg-sim.XXXXXX")
XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" \
XDG_STATE_HOME="$work/state" XDG_RUNTIME_DIR="$work/runtime" \
STG_SIMULATION=1 ~/.local/bin/steamos-time-guardian daemon --simulation
```

From a second shell emit all simulator events. Then stop it and restart the user service. Expected: production data unchanged.

## 10. Real game start/change/stop

Launch approved test game. Over SSH:

```bash
watch -n 2 'steamos-time-guardian --json status'
journalctl --user -fu steamos-time-guardian.service
```

Expected: name/App ID/source/confidence, increasing play time, no auxiliary-process duplicate sessions, one closed session on exit. Test game A→B change if practical.

Capture/redact Steam log format:

```bash
tail -n 100 ~/.local/share/Steam/logs/gameprocess_log.txt 2>/dev/null || \
tail -n 100 ~/.steam/steam/logs/gameprocess_log.txt 2>/dev/null
```

Add only sanitized fixtures after review.

## 11. Install and test Decky UI

When Decky is healthy:

```bash
cd "$HOME/stg-validation-src/steamos-time-guardian"
./scripts/install-user.sh --with-decky
```

Reload plugins/restart Steam through Steam UI after separate approval. Validate:

- Summary: today, remaining, timer, game, warning, restriction.
- Controller/touch timer controls.
- Weekly, History, Settings, Diagnostics pages.
- Clear service-unavailable state.
- QAM closed state does not poll rapidly.
- Diagnostic plugin heartbeat becomes recent.

## 12. Notifications

With a game active:

```bash
steamos-time-guardian timer start 2m --action notify_only
```

Expected: one notice per crossed threshold/exhaustion, no repeated tick spam, event history marks. Desktop path separately:

```bash
notify-send 'SteamOS Time Guardian validation' 'Desktop notification path'
```

Do not infer Game Mode success from Desktop success.

## 13. Suspend/resume

Start game/timer, note status, suspend with physical power button for at least two minutes, resume, then inspect:

```bash
steamos-time-guardian --json status
steamos-time-guardian --json history list --limit 5
steamos-time-guardian --json diagnose
```

Expected: suspend interval excluded; explicit/inferred events; socket/service recover; no duplicate open session. Avoid remote suspend initially because it can sever recovery.

## 14. Daily reset

Do not change system clock initially. Back up config and set reset a few minutes ahead with a reviewed patch:

```bash
cp ~/.config/steamos-time-guardian/config.json "$HOME/stg-config-before-reset-test.json"
steamos-time-guardian config patch @/path/to/reviewed-reset-patch.json
systemctl --user restart steamos-time-guardian.service
```

Keep game active over reset. Expected: old session closes `daily_reset`, new session opens under next accounting day, allowance resets. Restore through a validated patch. Time-zone/manual-clock tests require separate approval.

## 15. Controlled close (level 2)

Require explicit confirmation and a game with no unsaved progress. Keep force kill false:

```bash
steamos-time-guardian config patch \
  '{"restriction":{"level":2,"grace_seconds":60,"force_kill_enabled":false}}'
steamos-time-guardian timer start 2m --action close
```

Expected: warnings → expiration → grace → Decky/Steam close request → clean exit/history reason. If it remains, inspect safe failure. Do not enable broader signals just to pass.

Test verified `SIGTERM` fallback only after inspecting App ID/PIDs and obtaining approval. Do not test `SIGKILL` in first hardware session.

## 16. Level 3 cooperative block

Only after level 2 reliability and explicit approval. Expected: newly launched games are asked to close while Desktop Mode, settings, power, SSH, and uninstall remain accessible. Prove bonus/reset clears the state.

## 17. CPU, RAM, wakeups, disk, battery

Follow `docs/resource-usage.md`. Minimum:

```bash
pid=$(systemctl --user show -p MainPID --value steamos-time-guardian.service)
./tools/measure-resources.sh --pid "$pid" --duration 300
cat "/proc/$pid/io"
systemctl --user show steamos-time-guardian.service -p MemoryCurrent -p CPUUsageNSec -p TasksCurrent
```

Measure idle, active, QAM, Decky disconnected, suspend/resume, and soak. Record Deck model, battery state, TDP/frame cap, game, power, screen state. Targets: idle CPU <0.2%, RSS <60 MiB, no growth/per-second writes/observable delay—targets only, not claimed results.

## 18. Logs and support bundle

```bash
./scripts/diagnose.sh --bundle "$HOME/stg-support-validation.tar.gz"
tar -tzf "$HOME/stg-support-validation.tar.gz"
```

Expected: health/config/log excerpts, no session export, no secrets, home path redacted. Inspect manually.

## 19. SteamOS update persistence

Only during a future approved stable update: back up data, note status/checksums, update normally through Steam UI, reboot, rerun inventory/status. Expected: XDG data/unit remain; Decky may need its official repair flow; daemon remains independent.

## 20. Uninstall and rollback

```bash
./scripts/uninstall-user.sh --remove-decky
command -v steamos-time-guardian || true
systemctl --user status steamos-time-guardian.service --no-pager || true
ls ~/.config/steamos-time-guardian ~/.local/share/steamos-time-guardian
```

Expected: program/service/plugin removed, data retained. Reinstall and confirm history. Purge requires a final explicit approval and backup:

```bash
./scripts/uninstall-user.sh --remove-decky --purge-data --yes
```

## Validation report contents

Record device alias/model, SteamOS/channel/kernel/client/Decky versions, archive SHA-256, each command/result/timestamp, games/App IDs, detector source/confidence, notification evidence, resource measurements, enforcement sequence/signals, uninstall/rollback, unresolved blockers, and go/no-go recommendation.
