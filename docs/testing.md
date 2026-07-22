# Testing strategy

## Layers

- **Unit:** schedule, accounting, config, storage/migrations, notifications, enforcement verifier, Steam-log parser.
- **Integration:** real Unix socket client/server, concurrent calls, restart/incomplete-session recovery.
- **Plugin smoke:** compile TypeScript and run generated plugin in a mocked Decky/Steam runtime.
- **System smoke:** isolated XDG daemon in simulation; timer/game/suspend/history/diagnostics.
- **Hardware validation:** manual/SSH plan, never represented as simulation.

## Commands

```bash
./scripts/test.sh
./scripts/test.sh --coverage
./scripts/test.sh --python-only
./scripts/test.sh --plugin-only
./scripts/lint.sh
./scripts/smoke-test.sh
```

`test.sh` uses pytest when available and falls back to standard-library unittest. Coverage uses branch coverage and a 60% repository-wide minimum when installed; the safety-sensitive domain modules are expected to remain materially above that aggregate floor.

## Covered behavior

Remaining time, daily reset, weekday/unlimited/allowed periods, timer state, suspend gaps,
wall-clock changes, config/database migration, restart recovery, IPC validation/concurrency,
history/summaries/retention/clear/export, Activity buckets across four-hour and daily boundaries,
warning deduplication, all restriction modes, process verification, notification behavior,
detector errors/log parsing, and auxiliary PID grouping.

## Fixtures and simulator

`tests/fixtures/gameprocess_log.txt` contains sanitized representative Steam lines. Hardware validation may add anonymized current formats after review; never commit usernames, Steam IDs, home paths, secrets, or full live logs.

```bash
PYTHONPATH=daemon/src python3 tools/steam_deck_simulator.py --help
steamos-time-guardian simulate game_started --app-id 123 --name Test
steamos-time-guardian simulate game_changed --app-id 456 --name Other
steamos-time-guardian simulate suspend
steamos-time-guardian simulate resume
steamos-time-guardian simulate limit_reached
steamos-time-guardian simulate close_success
steamos-time-guardian simulate game_unresponsive
steamos-time-guardian simulate service_restart_checkpoint
```

The simulator validates orchestration/domain behavior, not Gamescope/Steam/Decky integration.

## Rules for new tests

Every compatibility change needs a fixture and negative case. Every schema change needs
migration/corruption tests. Activity heatmap changes must prove that suspend and material clock
gaps are omitted instead of inferred, and that the bucket sum never exceeds active monotonic time.
Every enforcement change must prove unrelated/same-name processes are not selected. Use
`FakeClock`, not sleeps.
