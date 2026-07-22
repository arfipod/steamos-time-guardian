# Changelog

All notable changes use [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

## [Unreleased]

### Planned
- Validation and compatibility fixes from a physical Steam Deck running the stable SteamOS channel.
- Optional PIN policy after the local threat model has been reviewed.

## [0.1.0] - 2026-07-22

### Added
- Standard-library Python user daemon with monotonic time accounting and SQLite persistence.
- Daily/weekly limits, reset time, exceptional adjustments, timers, warnings, history, JSON/CSV export.
- Unix-socket IPC with same-UID peer validation and event subscriptions.
- Composite Steam/Decky/procfs detector plus full simulator.
- Safe, configurable restriction levels with isolated enforcement adapters.
- Optional rootless Decky Quick Access Menu plugin and Desktop Mode TUI/CLI.
- Idempotent user install/uninstall scripts, CI, tests, diagnostics, support bundle, and documentation.
