# Architecture options and decision

Research date: **2026-07-22**. Scores are relative for this project: 1 poor, 3 acceptable, 5 strong.

## Options

1. **Decky-only plugin** — UI and backend live entirely under Decky.
2. **Desktop Mode application only** — conventional GUI/Flatpak-style app.
3. **Background user service only** — daemon plus CLI/notifications, no Game Mode panel.
4. **Hybrid service + optional Decky + Desktop UI** — selected.
5. **Steam launch wrappers/library modification** — inject a wrapper into every game or edit Steam shortcut/launch configuration.

## Comparison

| Criterion | Decky only | Desktop only | User service only | Hybrid | Launch wrappers |
|---|---:|---:|---:|---:|---:|
| Game Mode integration | 5 | 1 | 2 | 5 | 2 |
| Access during play | 5 | 1 | 2 | 5 | 1 |
| Installation simplicity | 3 | 4 | 4 | 3 | 1 |
| SteamOS-update persistence | 3 | 4 | 5 | 5 core / 3 Decky | 2 |
| CPU/memory/battery potential | 3 | 3 | 5 | 4 | 3 |
| Reliability of core state | 2 | 3 | 5 | 5 | 2 |
| Least privilege/security | 2–4 by flags | 4 | 5 | 5 core | 2 |
| Native notifications | 5 Game Mode | 4 Desktop | 3 Desktop | 5 combined | 2 |
| Active-game detection | 5 in Game Mode | 2 | 3–4 | 5 | 3 |
| Controlled restrictions | 3 | 2 | 3 | 4 | 3 |
| Maintainability | 2 | 4 | 5 | 4 | 1 |
| Third-party dependency | High | Low/medium | Low | Optional/high only for QAM | High internal coupling |
| Update breakage risk | High | Medium | Low | Low core / high adapter | Very high |

## Analysis

### Decky-only

Decky is the best current route to a controller-accessible Quick Access Menu panel and Steam toast APIs. However, it is third-party homebrew, uses compatibility layers around internal Steam frontend objects, and its project documents that it can disappear after SteamOS updates. Making it the only storage/accounting process would couple history correctness to the Steam client/plugin lifecycle. This project does not use a root flag.

### Desktop-only

A KDE/Flatpak app would persist in the writable user area, but it is not conveniently accessible inside a Game Mode session. Desktop notifications are not a reliable substitute for Game Mode toasts. An always-open GUI also offers little benefit over a small service and may increase memory use.

### User service only

This is the strongest core: `systemd --user`, XDG data, SQLite, Unix socket, no root changes. It can observe Steam logs/process environments and show Desktop notifications. It cannot provide a first-class QAM or the highest-confidence focused-app signal by itself.

### Hybrid — selected

The daemon owns all durable and safety-sensitive responsibilities. Decky is a replaceable interface/detector/Steam-close adapter. Desktop CLI/TUI remains available when Decky or Steam is unavailable. This adds component count, but the interfaces are narrow and testable. It best satisfies in-game accessibility without accepting Decky as a single point of failure.

### Launch wrappers / Steam-library interception

Wrapping every executable is fragile for Proton, native games, launchers, emulators, and non-Steam shortcuts. It modifies user library configuration, creates compatibility risk, and can be bypassed by launch-option changes. It is rejected. Global input interception, Gamescope patching, PAM changes, firewalling, and root filesystem changes are also rejected as disproportionate and unsafe.

## Decision

Use the hybrid architecture with these boundaries:

- daemon and data remain useful without Decky;
- Decky installation is explicit (`--with-decky`), rootless, and removable;
- Steam-internal APIs remain encapsulated in the Decky adapter;
- process signals remain encapsulated in enforcement and fail closed;
- no mutable-root, system service, Steam library modification, or network API;
- physical validation is required before controlled close.
