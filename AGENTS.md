# AGENTS.md — SteamOS Time Guardian

## Mission

Maintain `steamos-time-guardian`, a local, low-overhead SteamOS/Steam Deck play-time tracker with optional safe restrictions. Preserve user control, recovery paths, privacy, and compatibility with SteamOS's immutable-system model.

The repository is an alpha suitable for conventional-Linux simulation and ready for a carefully controlled physical Steam Deck validation phase. Never state that hardware behavior is validated unless the exact check was performed and recorded.

## Architecture and components

- `daemon/src/stg/`: dependency-free Python 3.11+ daemon, domain engine, SQLite, Unix RPC, detector adapters, notifications, and enforcement.
- `decky-plugin/`: optional controller-friendly Quick Access Menu frontend and rootless Python bridge.
- `desktop-ui/`: `.desktop` launcher and icon for the curses TUI.
- `config/`: defaults example and JSON Schema.
- `systemd/`: hardened `systemd --user` unit.
- `scripts/`: supported build, test, install, uninstall, diagnostics, package, and smoke workflows.
- `tools/`: repository tooling, simulator, support bundle, and resource measurement.
- `tests/`: unit/integration tests and sanitized Steam-log fixtures.
- `docs/`: design, ADRs, security, validation, and research records.

The daemon is the source of truth. Decky is an optional adapter, never a required dependency for tracking, storage, or Desktop Mode management.

## Safety invariants

1. Normal runtime is unprivileged. Do not add `sudo`, a system service, setuid binaries, capabilities, or root Decky flags without an approved ADR and explicit user authorization.
2. Do not disable SteamOS read-only mode or modify `/usr`, `/etc`, or the immutable root.
3. Never expose the API on TCP, UDP, WebSocket, or a network interface. Keep the mode-`0600` Unix socket and same-UID peer checks.
4. Do not construct shell commands from user input.
5. Tracking and enforcement must remain separate. A detector/storage failure must not trigger aggressive enforcement.
6. Never kill by process name. Process fallback may target only same-UID PIDs whose environment verifies the expected Steam App ID.
7. `SIGKILL` remains opt-in and false by default.
8. Level 3 must never block Desktop Mode, Steam settings, shutdown, reboot, SSH, terminal access, uninstall, or recovery.
9. No telemetry, remote accounts, cloud sync, advertising, or outbound data transfer.
10. Never make destructive changes to a real Steam Deck without explicit approval of that exact action.

## Dependencies

Runtime has no PyPI dependency. Development tools are pinned in `pyproject.toml`. The Decky frontend build uses Node.js 22 and TypeScript 5.8.3; generated `dist/index.js` is committed so installation does not require Node on Steam Deck.

```bash
./scripts/bootstrap-dev.sh          # local package, offline-compatible
./scripts/bootstrap-dev.sh --online # pinned dev tools and TypeScript
```

Do not casually upgrade Decky-related assumptions. Re-check the official Decky repositories and current SteamOS stable release before compatibility changes.

## Build, tests, lint, and development

```bash
./scripts/build.sh
./scripts/test.sh --coverage
./scripts/lint.sh
./scripts/format.sh
./scripts/format.sh --check
./scripts/start-dev.sh --reset
./scripts/smoke-test.sh
./scripts/package.sh
```

## Coding conventions

- Python: 3.11 syntax, complete annotations, small modules, explicit exceptions, standard library first, Ruff and strict mypy clean.
- Domain code must not import Decky, systemd, UI, or process-control modules.
- Infrastructure adapters implement narrow interfaces and emit typed events.
- All mutable daemon actions are serialized by the service lock and database transactions.
- TypeScript: avoid `any`; isolate undocumented Steam/Decky objects behind runtime guards and the compatibility adapter.
- Shell: `#!/usr/bin/env bash`, `set -euo pipefail`, project-root discovery through `scripts/common.sh`, quoted variables, idempotence, clear errors, and `--help` where applicable.
- JSON schemas and defaults change together. Increment schema versions and add migration tests.
- Add or update tests for every behavioral bug.
- Comments explain compatibility hazards or safety rationale, not obvious syntax.

## Commit policy

Use small, reviewable commits with imperative subjects:

- `fix: preserve timer state across daemon restart`
- `feat: add non-Steam detection fixture`
- `docs: record SteamOS compatibility findings`
- `test: cover DST reset transition`

Do not mix generated plugin output with unrelated refactors. When `decky-plugin/src/` changes, rebuild and commit `decky-plugin/dist/index.js` and its source map in the same commit.

## Files requiring special justification

- `systemd/steamos-time-guardian.service`: privilege and filesystem boundary.
- `daemon/src/stg/enforcement.py`: process termination and recovery risk.
- `daemon/src/stg/ipc.py`: local authentication boundary.
- `daemon/src/stg/storage.py`: migrations and history integrity.
- `daemon/src/stg/config.py` plus `config/schema.json`: schema compatibility.
- `decky-plugin/src/index.tsx`: undocumented Steam compatibility layer.
- `scripts/install-user.sh` and `scripts/uninstall-user.sh`: persistent device changes.
- `tools/package_project.py`: delivered archive integrity.
- `docs/sources.md`: research claims and dates.

Never edit generated `decky-plugin/dist/` directly. Change source, build, then inspect the generated diff.

## Working without a Steam Deck

Use `STG_SIMULATION=1`, `./scripts/start-dev.sh`, and `tools/steam_deck_simulator.py`. Keep state under `.dev/`. Do not create fake claims about Game Mode rendering or physical suspend behavior. Extend deterministic fixtures rather than relying on live Steam installations in CI.

## Physical validation over SSH

Before connection:

1. Confirm device, SteamOS channel, backup state, test game, Decky choice, and maximum enforcement level.
2. Start with read-only commands from `docs/steam-deck-validation-plan.md`.
3. Copy the archive to the user's home, verify SHA-256, and extract there.
4. Run tests/build/smoke before installation.
5. Use `install-user.sh --dry-run`, then install without Decky and with level 0 first.
6. Validate status/history/suspend and resource use.
7. Install/reload Decky only after daemon validation.
8. Exercise level 2 only with explicit approval and an expendable game; keep force kill disabled.
9. Record actual commands, outputs, versions, and observations in a dated validation report.
10. Prove uninstall and recovery before completion.

### Prohibited real-device actions without explicit approval

Do not run `steamos-readonly disable`, `sudo pacman`, filesystem formatting, partition changes, factory reset, broad `pkill`/`killall`, Steam configuration deletion, database purge, Decky uninstall, Steam client restart, forced reboot, or forced game kill unless the user explicitly approves the exact action after being told the risk.

## Completion checklist

- [ ] Architecture and safety invariants still hold.
- [ ] No network listener, telemetry, secret, credential, or environment-specific path was added.
- [ ] Defaults, schema, migrations, examples, and docs agree.
- [ ] Unit/integration tests cover the change.
- [ ] `./scripts/format.sh --check` passes.
- [ ] `./scripts/lint.sh` passes with installed tools.
- [ ] `./scripts/test.sh --coverage` passes.
- [ ] `./scripts/build.sh` passes and generated Decky output matches source.
- [ ] `./scripts/smoke-test.sh` passes.
- [ ] Installer/uninstaller remain idempotent and non-destructive by default.
- [ ] `./scripts/package.sh` succeeds and ZIP integrity is checked.
- [ ] Hardware-only behavior is labelled unvalidated unless actually tested.
- [ ] Any real-device action and rollback are documented.
