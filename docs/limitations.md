# Known limitations and risks

## Hardware validation pending

No physical Steam Deck was available. Game Mode rendering, current Steam client internals, real
suspend/resume, notifications over games, controlled close, a real `systemd --user` activation,
update persistence, and battery impact remain unvalidated.

## Decky and Steam internals

Decky Loader is third-party. The QAM references Steam frontend objects such as running-app state, lifecycle notifications, and terminate-app. These are not stable public Valve APIs. They are isolated and can break without notice.

## Detection

- Steam's process-log format is empirical, not promised.
- Non-Steam shortcuts may produce App ID 0.
- Emulators can identify the emulator/shortcut, not the ROM.
- Multiple simultaneous Steam apps/streaming/launchers can make foreground ambiguous.
- Desktop Mode focus cannot be proven by Steam log/procfs alone.
- Hardened processes may hide environments.

False negatives are preferred over dangerous false positives.

## Restrictions

- Level 3 is not administratively impossible to bypass.
- The owner can stop/uninstall/edit the service.
- Steam close may not save progress; games can ignore close/SIGTERM.
- The Decky close-result callback is diagnostic in the MVP; enforcement cancels when detection
  observes that the game actually exited and otherwise follows the configured fixed timeout.
- Force kill risks data loss and is disabled.
- Process fallback refuses App ID 0/ambiguity and may fail to close.
- Steam library/launch-option blocking is deliberately absent.

## Notifications/time/data

Freedesktop notifications may not appear over Game Mode. DST/nonexistent local reset times have policy ambiguity despite deterministic `zoneinfo` behavior. SQLite/WAL reduces but does not eliminate storage loss; a hard crash can undercount up to the checkpoint interval.

The Activity heatmap is not backfilled from older sessions: their monotonic duration cannot be
assigned reliably to wall-clock hours after a suspend or daemon gap. It starts collecting after
the schema-3 upgrade and omits intervals with a material wall-clock discrepancy rather than
showing guessed activity. Daily totals and game rankings continue to use all retained sessions.

## Packaging

Runtime assumes Python 3.11+ on target SteamOS and must be confirmed. The plugin bundle targets the observed Decky model; store submission and current-device compatibility review are pending.
