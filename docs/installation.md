# Installation and upgrade

## Principles

The installer modifies only the current user's home/XDG locations. It does not use root privileges, disable SteamOS read-only mode, invoke `pacman`, install Decky Loader, restart Steam, or delete existing data.

## Preflight

```bash
python3 --version          # must be 3.11+
node --version             # Node 22 only needed to rebuild Decky
./scripts/build.sh
./scripts/test.sh
./scripts/smoke-test.sh
./scripts/install-user.sh --dry-run
```

The committed Decky bundle means Node is not required for installation, only build verification.

## User installation

```bash
./scripts/install-user.sh
```

Program files:

```text
~/.local/lib/steamos-time-guardian/
~/.local/bin/steamos-time-guardian
~/.config/systemd/user/steamos-time-guardian.service
~/.local/share/applications/steamos-time-guardian.desktop
~/.local/share/icons/hicolor/scalable/apps/steamos-time-guardian.svg
```

Persistent files installed by this script:

```text
~/.config/steamos-time-guardian/config.json
~/.local/share/steamos-time-guardian/guardian.db
~/.local/state/steamos-time-guardian/guardian.jsonl
```

These are the standard XDG default locations. The installer and installed user unit use those
fixed defaults so that the unit's sandbox and writable paths stay aligned. Direct development or
manual daemon execution honors explicitly supplied `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
`XDG_STATE_HOME`, and `XDG_RUNTIME_DIR` values.

## Optional Decky installation

Decky Loader must already be installed and reviewed:

```bash
./scripts/install-user.sh --with-decky
```

The installer checks `${DECKY_HOME:-$HOME/homebrew}/plugins`, copies the plugin to `SteamOS-Time-Guardian`, and tells the user to reload plugins/restart Steam through its UI. No root Decky flag is used.

Without Decky, the service, simulator, CLI/TUI, history, Desktop notifications, Steam-log detection, and procfs fallback work. QAM access, Steam toasts, and the preferred Steam close request are unavailable.

## Service

```bash
systemctl --user daemon-reload
systemctl --user enable --now steamos-time-guardian.service
systemctl --user status steamos-time-guardian.service
```

The unit uses `NoNewPrivileges`, strict system protection, read-only home by default, an isolated
runtime directory, Unix-only address families, and explicit writable app paths. If the user
manager is unreachable, the installer leaves files and explains manual daemon startup.

## Upgrade and rollback

Build and rerun the installer. It stages new files, stops the old service, moves program paths to timestamped backups, installs by rename, preserves data, restarts, and restores backups on pre-commit error.

```bash
./scripts/build.sh
./scripts/install-user.sh --with-decky   # omit when not wanted
```

Before major upgrades:

```bash
cp -a ~/.config/steamos-time-guardian ~/.config/steamos-time-guardian.backup
cp -a ~/.local/share/steamos-time-guardian ~/.local/share/steamos-time-guardian.backup
```

Configuration/database migrations happen in daemon code and have tests.

## No-start/manual mode

```bash
./scripts/install-user.sh --no-start
~/.local/bin/steamos-time-guardian daemon
```

## Verify

```bash
./scripts/status.sh
steamos-time-guardian --json status
steamos-time-guardian --json diagnose
journalctl --user -u steamos-time-guardian.service --since -10m
```

Expected: active user service, runtime socket, DB quick check `ok`, database schema version 3, restriction level 0.

## Uninstall while retaining data

```bash
./scripts/uninstall-user.sh --remove-decky
```

This removes program/unit/launcher/icon and optionally plugin files, while preserving configuration/database/logs.

## Complete purge

```bash
./scripts/uninstall-user.sh --remove-decky --purge-data --yes
```

`--yes` prevents accidental deletion. Export/backup history first.

## SteamOS persistence rationale

SteamOS image updates can replace non-Flatpak root modifications. This project avoids that area. Home/XDG is the persistent location. Decky itself can still require repair after an update; that does not remove daemon XDG data.
