# Security model

## Scope and non-goals

This application helps a device owner follow self-imposed limits. It is not an anti-tamper boundary. A user who owns the Linux account or has administrative access can stop the service, edit files, replace the plugin, or boot another environment. The design prioritizes safe recovery over resistance to the owner.

## Assets and trust boundaries

Assets are local history/preferences, accounting integrity, Game/Desktop availability, and unrelated user processes/files. Trust boundaries are CLI/TUI/Decky to the Unix socket, daemon to Steam/Decky compatibility APIs, daemon to same-user `/proc`/signals, and daemon to SQLite/config files.

## Controls

### Least privilege

The daemon runs as `systemd --user`. No root flags, capabilities, polkit helper, sudo, root filesystem change, or system-wide service is installed. The unit uses `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=read-only`, private `/tmp`, a mode-`0700` `RuntimeDirectory`, `RestrictAddressFamilies=AF_UNIX`, and explicit writable XDG/runtime paths.

### Local-only IPC

No network socket is created. The Unix socket is in the user-private runtime directory, mode `0600`, with Linux peer UID verification. Requests are bounded/validated. No secret or reusable token is necessary.

### Input validation

Configuration rejects unknown keys and validates ranges, weekdays, time zones, periods, and enums. RPC text/list/integer fields have length/count bounds. SQL uses parameters. Process control does not accept executable commands.

### Enforcement safety

- Tracking and enforcement are separate modules.
- Process fallback requires an expected nonzero App ID.
- Candidate PIDs must belong to daemon UID.
- `/proc/<pid>/environ` must contain the same Steam App ID.
- No process-name-only targeting, broad process groups, `pkill`, or `killall`.
- Steam close is attempted through Decky first.
- `SIGTERM` is fallback; `SIGKILL` is disabled by default.
- Enforcement cancels on game stop, allowance restoration, reset, or shutdown.
- Desktop Mode, power, settings, terminal, SSH, and uninstall remain accessible.

### Privacy

All data remains local. No telemetry, analytics, cloud, account, phone control, or Internet requirement exists. Logs avoid raw environments. Support bundles exclude session history and redact home paths.

## Threats and mitigations

| Threat | Mitigation / residual risk |
|---|---|
| Other local user calls daemon | Socket mode and peer UID check; the same account remains trusted. |
| Malicious same-user plugin | Input validation limits behavior; process kill still requires App-ID verification. |
| Steam internal API changes | Adapter failure is non-fatal; no uncertain enforcement. |
| PID reuse | UID/environment re-read immediately before signal; race cannot be eliminated completely. |
| Corrupt config/database | Atomic writes, quarantine, transactions, checks, backup guidance. |
| Symlink/path manipulation | Fixed XDG app paths and user-only modes; hostile same-account behavior is out of scope. |
| Owner denial/bypass | Explicitly unavoidable for a user service. |
| Sensitive support bundle | History excluded and paths redacted; user still inspects before sharing. |

## Responsible deployment

Start at level 0. Validate detection/notifications, then level 1. Test level 2 only with a disposable game, force kill disabled, and physical/Desktop recovery. Level 3 remains cooperative and requires explicit approval after repeated level-2 success.
