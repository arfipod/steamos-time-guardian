# Local validation report

Validation date: **2026-07-22**. Project version: **0.1.0**.

This report describes only conventional-Linux and simulated validation. No command in this report
was run on a physical Steam Deck, in Gamescope/Game Mode, or against a real Decky Loader instance.

## Validation environment

| Component | Observed version |
|---|---|
| Python | 3.13.5 |
| Python SQLite library | 3.46.1 |
| pytest | 9.0.2 |
| pytest-cov | 7.0.0 |
| coverage.py | 7.13.3 |
| Node.js | 22.16.0 |
| npm | 10.9.2 |
| TypeScript compiler | 5.8.3 |

The supported runtime floor remains Python 3.11. CI intentionally runs Python 3.11 and Node 22.
Pinned development versions for a reproducible connected environment are in `pyproject.toml` and
`.github/workflows/ci.yml`.

## Commands and results

```text
python3 -m pytest -q
64 passed, 11 subtests passed

./scripts/test.sh --coverage
64 passed, 11 subtests passed
Total branch coverage: 67.70%; configured minimum: 60%
Decky build and mocked-runtime smoke test: passed

(cd decky-plugin && npm test)
TypeScript build: passed
Generated dist/index.js: 20,392 bytes
Mocked Decky/Steam runtime smoke test: passed

./scripts/format.sh --check
passed

./scripts/lint.sh
repository integrity/secret/path lint: passed
shell syntax: passed
Python compilation: passed
Decky TypeScript type check: passed
Ruff: not run locally (tool unavailable)
mypy: not run locally (tool unavailable)

./scripts/build.sh
passed

./scripts/smoke-test.sh
simulation daemon, IPC, timer, game, suspend/resume, history, and diagnostics: passed
```

Direct attempts to install Ruff and mypy were blocked by the validation container's DNS/network
resolution. Their absence is reported by `lint.sh`, not silently treated as execution. The CI
workflow installs the pinned versions and treats their findings as failures.

## Installer and uninstaller sandbox

An isolated temporary `HOME` and `DECKY_HOME` were used without root access. The following behavior
was exercised:

1. Install with the optional prebuilt Decky plugin.
2. Repeat the install and verify the existing configuration is preserved.
3. Start the installed daemon manually in simulation mode and query it through the installed CLI.
4. Uninstall while preserving configuration and data.
5. Repeat uninstall to verify idempotence.
6. Reinstall and verify preserved configuration remains usable.
7. Purge with the explicit `--purge-data --yes` pair and verify config/data/state removal.

All checks passed. The temporary environment intentionally had no reachable per-user systemd
manager, so actual `systemctl --user enable --now` behavior remains a real-session validation item.

## Support bundle validation

A live simulated game with a private display name and a custom Steam-log path was created, then:

```text
./scripts/diagnose.sh --bundle support.zip
python3 -m zipfile -t support.zip
```

The archive passed integrity testing, had mode `0600`, contained no database/history file, did not
contain the active game name, and replaced the custom detector path with `$REDACTED_PATH`.

## systemd unit verification

`systemd-analyze verify systemd/steamos-time-guardian.service` recognized the hardening directives.
It returned the expected missing-executable warning because `%h/.local/bin/steamos-time-guardian`
was not installed into the validation container's real home. Startup under a real user manager is
therefore not claimed here.

## Packaging verification

The release procedure builds a deterministic project ZIP and Decky ZIP, writes SHA-256 sidecars,
tests ZIP members, extracts the project into a clean temporary directory, and reruns format, lint,
tests, build, smoke, and installer dry-run from the extracted tree. The final delivery audit also
checks for cache files, bytecode, secrets, environment-specific absolute paths, and unreferenced
missing files.

## Still pending on a real Steam Deck

- Exact stable-image Python/systemd environment.
- Decky installation path, backend UID, QAM rendering, controller/touch navigation, and reconnect.
- Current Steam frontend `MainRunningApp`, lifecycle, toaster, and `TerminateApp` compatibility.
- Current `gameprocess_log.txt` path and line formats.
- Real foreground transitions for Steam, non-Steam, emulator, launcher, and streaming cases.
- Desktop and Game Mode notifications.
- Suspend/resume, timezone change, DST, and accounting-day reset over real sleep cycles.
- Graceful and fallback close behavior with save-state-sensitive games.
- CPU, RAM, wakeups, disk writes, thermals, and battery impact.
- Persistence through an actual SteamOS update and complete rollback/uninstall.

Use `docs/steam-deck-validation-plan.md` for the controlled SSH phase. Keep restriction level 0 and
forced termination disabled until the detection and close matrices pass.
