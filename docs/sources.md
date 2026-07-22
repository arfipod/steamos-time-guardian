# Research sources

Research date: **2026-07-22**. Priority was Valve/Steam, official Decky repositories, Freedesktop/systemd specifications, Linux/Python/SQLite primary documentation, then official-project implementation evidence. Recheck before physical installation.

## SteamOS stable and Desktop Mode

- The newest Valve stable-channel notice found was **SteamOS 3.8.16**. Official notice: https://store.steampowered.com/news/app/1675200/view/698770449667981856
- The larger **SteamOS 3.8.10** transition updated the Arch base, Linux kernel 6.16, KDE Plasma 6.4.3, and made Wayland the Desktop Mode default. Valve Steam Deck news/release index: https://store.steampowered.com/news/app/1675200
- Later 3.8.x notices are maintenance releases; architecture decisions use 3.8 base capabilities and 3.8.16 as the stable verification point.

## Immutable root and persistence

Valve's Desktop FAQ warns that non-Flatpak packages/root-image changes can be removed by SteamOS updates. It documents `steamos-readonly disable` with explicit warnings. This project does not use it: https://help.steampowered.com/faqs/view/671A-4453-E8D2-323C

Conclusion: install under home/XDG and use a user service; do not depend on `pacman` runtime packages.

## Game Mode, QAM, and Decky

- Decky Loader features, installation, update persistence claim, and documented disappearance/repair after some SteamOS updates: https://github.com/SteamDeckHomebrew/decky-loader
- Release page showed stable **v3.2.6** (2026-06-24) at research time: https://github.com/SteamDeckHomebrew/decky-loader/releases
- Plugin template/distributable layout and incomplete-docs warning: https://github.com/SteamDeckHomebrew/decky-plugin-template
- Loader API (`callable`, events, toaster, quick-access visibility): https://github.com/SteamDeckHomebrew/loader-api
- Compatibility typings for `Router.MainRunningApp`, app-lifetime notifications, and terminate-app: https://github.com/SteamDeckHomebrew/decky-frontend-lib

Qualification: those Steam frontend objects are compatibility typings around internal client behavior, not a stable public Valve SDK. Non-Steam lifecycle notifications can expose App ID 0. The project isolates them and keeps daemon fallbacks.

## Notifications, systemd, XDG, IPC

- Freedesktop Desktop Notifications 1.3: https://specifications.freedesktop.org/notification-spec/latest/
- `pam_systemd` / `$XDG_RUNTIME_DIR`: https://www.freedesktop.org/software/systemd/man/latest/pam_systemd.html
- User services: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- Journal: https://www.freedesktop.org/software/systemd/man/latest/journalctl.html
- XDG Base Directory: https://specifications.freedesktop.org/basedir-spec/latest/
- Unix sockets and `SO_PEERCRED`: https://man7.org/linux/man-pages/man7/unix.7.html

Conclusion: user unit, persistent XDG config/data/state, ephemeral mode-0600 Unix socket, no HTTP/network API.

## Detection evidence

Steam's Linux `gameprocess_log.txt` contains App-ID/PID tracking lines (`adding PID`, `no longer tracking`, `Remove ... from running list`). The format is observed in Valve's Steam-for-Linux issue repository, not documented as stable: https://github.com/ValveSoftware/steam-for-linux/issues

Steam-launched processes commonly expose `SteamAppId`, `SteamGameId`, and Proton's `STEAM_COMPAT_APP_ID`. The fallback groups processes by ID and never trusts executable name alone.

Conclusion: combine Decky focus/lifetime, Steam log events, and slow procfs fallback; document non-Steam/emulator limits and collect current hardware fixtures.

## Time and persistence primitives

- Python monotonic clock: https://docs.python.org/3/library/time.html#time.monotonic
- Python `zoneinfo`: https://docs.python.org/3/library/zoneinfo.html
- SQLite WAL: https://www.sqlite.org/wal.html
- SQLite atomic commit: https://www.sqlite.org/atomiccommit.html

Conclusion: elapsed duration uses monotonic time; wall time defines accounting day; SQLite WAL and periodic checkpoints limit writes.

## Assumptions requiring hardware re-verification

1. Python 3.11+ on target stable image.
2. User systemd availability in Game/Desktop sessions.
3. Exact Steam log path/format.
4. Decky backend UID/environment and user-socket access.
5. Current Steam frontend running/lifetime/terminate API shapes.
6. Game Mode toaster/controller behavior.
7. Non-Steam/emulator metadata.
8. Suspend/resume delivery and timing.
9. Home path persistence through a real update.
