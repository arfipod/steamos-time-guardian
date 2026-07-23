# Steam Deck validation report — 2026-07-22

## Scope and approvals

- Device owner confirmed a current backup.
- Approved disposable test game: Celeste.
- Maximum requested restriction level: 2. Force kill remains disabled.
- This report excludes host addresses, credentials, and private game history.

## Read-only inventory

| Item | Observed value |
| --- | --- |
| Account | `deck` (UID 1000) |
| SteamOS | 3.8.16, build 20260716.1, Steam Deck variant |
| Kernel | 6.16.12-valve24.5-1-neptune-616-gb2f7cfe85e45 |
| Python | 3.13.5 |
| systemd | 257.7 |
| Free home storage | 174 GiB |
| Decky before validation | Not installed; no `~/homebrew/plugins` directory detected |
| Decky after owner installation | 3.2.6 stable, `plugin_loader.service` active |

The device version matches the stable baseline recorded in the validation plan. No update was
performed.

## Package and pre-install validation

- Package checksum verified: `steamos-time-guardian-0.1.0.zip` SHA-256
  `97c15f145dbf0adf0521bc3462f35830abec2eb702b4e270cb0029b50f322d41`.
- Both the project ZIP and Decky-plugin ZIP passed `python3 -m zipfile -t` on the build host;
  the project ZIP also passed on the Deck.
- Host validation with Node 22.23.1 and TypeScript 5.8.3: 64 Python tests passed at 67.79%
  branch coverage; Decky mocked-runtime smoke test passed; simulator smoke test passed.
- On the Deck, a temporary virtual environment in the extracted validation source ran all 64
  Python tests successfully under Python 3.13.5; the simulator smoke test also passed.
- The archive records executable shell scripts, but Python's `zipfile` extractor does not restore
  those Unix mode bits. The validation source's `scripts/` and `tools/` shell files were explicitly
  set executable before running the supplied commands; the validation plan now includes that step.
- A scan of `scripts/`, `systemd/`, and `packaging/` found no `steamos-readonly` or
  `sudo pacman` mutation path.

## Installed daemon

The daemon was installed only in the `deck` user's XDG paths and enabled as the user service.
The first IPC attempt raced the service start; a subsequent health check confirmed the service
and socket were present.

| Check | Result |
| --- | --- |
| Service | active (`steamos-time-guardian.service`) |
| Runtime directory | mode `0700` |
| Unix socket | mode `0600` |
| Database quick check | `ok`, schema 2 |
| Memory at check | 16.7 MiB |
| Restriction level | 0 |
| `force_kill_enabled` | `false` |
| Decky heartbeat before installation | not recent (expected: Decky is absent) |

No game was launched, no notification was inferred to have rendered in Game Mode, no suspend was
performed, and no level-2 close or signal fallback was exercised.

## Support bundle

A redacted support bundle was created at `~/stg-support-validation.zip` with mode `0600`. It is a
ZIP archive (not a tarball) containing the manifest, diagnostics, sanitized configuration, platform
details, user-service status, journal excerpt, and daemon-log tail. ZIP integrity passed; the
generator reports that database, session history, active game identity, and credentials are
excluded. Its contents were not exported from the device.

## Decky validation and remaining work

The official Decky installer was downloaded for inspection only and was not executed remotely. It
creates a root-owned system service, writes `/etc/systemd/system`, and removes/replaces
`~/homebrew/services`; the owner performed the Decky installation locally instead.

On this Decky release, `~/homebrew/plugins` is owned by `root`, which makes the normal
unprivileged `install-user.sh --with-decky` copy fail. With the owner's explicit approval, the six
already-verified plugin files were copied once with `sudo install` to the existing protected
directory. No owner or global permission was changed, no file under `/etc` was changed, and the
plugin manifest retained an empty `flags` array.

Decky hot-reload logged `Loaded SteamOS Time Guardian` and the plugin backend logged that its
rootless bridge started. The daemon then reported `decky_plugin_recent: true` while retaining its
same-user `0600` Unix socket. This validates loader discovery and the local bridge connection.

The owner supplied a Game Mode photo showing the SteamOS Time Guardian QAM panel rendered and
controller navigation available. The photo preceded the game launch, so its `None detected` value
was expected at that moment.

## Real-game and notification validation

Celeste was launched in Game Mode. Steam recorded App ID `504230` and a tracked launcher PID; the
daemon first recorded the Steam-log start event and then promoted the active game to Decky source
with confidence `1.0`. The live status showed increasing play time and the plugin heartbeat stayed
recent.

A two-minute `notify_only` timer was started while Celeste was active. The daemon recorded the
one-minute warning, expiration, persistent exhaustion notification, and timer-expired state. It
did not request a close and Celeste remained active, as required for restriction level 0. The timer
was then cancelled, returning the restriction state to `level 0 / reason none`. The owner visually
confirmed that the Game Mode toasts rendered.

An unexpected extra warning was also recorded immediately at timer start: a two-minute timer
crossed the configured five-minute threshold and displayed `5 minutes remaining`. This is a
notification-threshold UX defect to fix before release. It did not cause enforcement or process
control.

The owner then suspended the Deck with the physical power button and resumed with Celeste still
open. The daemon recorded paired inferred suspend/resume events with a 113-second gap. Across 179
seconds of wall time, play accounting increased by only 64 seconds, excluding the suspend interval.
Celeste remained active; the user service stayed active and its `0600` socket recovered.

Celeste was then exited normally. One session, lasting 367 seconds, closed with reason
`steam_log_removed_from_running_list`; the Decky lifetime event also reported the app stopped.
The final status had no active game and no Celeste process remained.

## Level-2 attempt aborted safely

The owner gave fresh approval for a level-2 test. The configuration patch itself reported that no
restart was recommended, but the validation command unnecessarily restarted the user daemon.
That shutdown closed only the daemon's current session; Celeste continued running. On restart, the
service did not recover the already-running game from Decky or its procfs fallback, even though an
isolated same-user `ProcfsDetector` scan identified App ID `504230` and its five related PIDs.

The two-minute close timer never consumed time because the service had no active game. It was
cancelled before expiry and the configuration was immediately restored to level 0, with force kill
disabled and the process-signal fallback restored to its previous value. No Steam close request,
SIGTERM, SIGKILL, or other process-control action was sent. This is a restart-recovery defect that
must be fixed and tested before approving enforcement after a daemon restart.

## Level-2 controlled-close validation

Celeste was then normally relaunched, producing fresh Steam-log and Decky lifecycle start events.
The level-2 patch was applied live without restarting the daemon: 60-second grace, force kill
disabled, and `safe_process_fallback` disabled. A two-minute `close` timer emitted the one-minute
and exhaustion notifications, activated level 2, and waited the full grace period.

At grace expiry, the daemon recorded `enforcement.close_requested`; Decky reported success with
`Steam close requested`. Steam removed Celeste from its running list and the game session closed
normally 0.49 seconds later. No Celeste process remained. No `SIGTERM`, `SIGKILL`, or process
fallback was enabled or sent.

Immediately after the test, the expired timer was cancelled and the configuration was restored to
level 0, force kill disabled, and the original process-fallback setting. The user service remained
active.

The remaining hardware-only checks are:

1. Fix and test active-game recovery after daemon restart.
2. Validate Desktop Mode TUI navigation and controller/touch controls for every QAM page.
3. Validate the daily-reset transition with a reviewed, temporary reset-time patch.
4. Measure the idle/active resource matrix and soak behavior.
5. Prove uninstall/recovery in a separately approved maintenance window; it is intentionally not
   run now because the owner wants this working installation retained.

## Activity and QAM-selection update

The owner subsequently approved an in-place update to add the compact Activity view and correct
Decky's view selector. The validated project archive had SHA-256
`4f00d0bc09f76d673d529df5d71d97c0dd278ce6c7adc389253f76e8c7f0694a` and passed a ZIP
integrity check on the Deck. Its 74 Python tests passed under Python 3.13.5 using the existing
local validation environment; the Python build, simulation smoke test, and `install-user.sh
--dry-run` also passed. That environment did not include `pytest-cov`, so the device test run did
not produce coverage figures.

Before installing, the user service was stopped and coherent copies of its configuration and data
were retained under the update staging directory. The normal installer then upgraded the user
daemon without the Decky option. The stop took its configured timeout and systemd sent `SIGKILL`
to the old daemon processes; no game process was targeted or terminated. The replacement service
was active, recreated its mode-`0600` socket, and reported database `quick_check: ok` with schema
version 3, restriction level 0, and force kill disabled.

The existing root-owned Decky plugin directory was checked to be a real directory, not a symlink,
and both its old and new manifests had `flags: []`. A recovery copy of exactly six files was kept
in the update staging directory. With the owner's authorization, those six files (`main.py`,
`plugin.json`, `package.json`, `LICENSE`, `dist/index.js`, and `dist/index.js.map`) were replaced
with `root:root` ownership and mode `0644`; no recursive ownership or permission change was made.
`plugin_loader.service` was then restarted. Decky logged `Loaded SteamOS Time Guardian` and the
rootless bridge started. Decky's controlled reload waited five seconds for the prior bridge and
then killed that prior plugin process; this did not target a game. The reload also refreshed its
Steam web-helper frontend, but did not restart the Steam client service.

The new local RPC `summary.activity` returned the retained seven-day totals and top game correctly.
Its heatmap deliberately reported unavailable for existing historical sessions: it begins collecting
truthful four-hour buckets only after this update, rather than inferring past clock-time activity.
The final pending physical check is to select Timer, Activity, and another QAM page in Game Mode
and confirm each remains selected instead of returning to Summary.

## Current daily policy

At the owner's request, the live configuration was atomically updated through the local CLI/RPC to
allow 45 minutes on Monday through Friday and 120 minutes on Saturday and Sunday. It retained the
existing system timezone, midnight accounting reset, empty allowed-period list, and level-0
restriction policy. The immediate Thursday status correctly reported a 2,700-second daily limit.
Level 0 continues to record and notify without closing a game; no enforcement level was changed.

## Spanish and English UI update

At the owner's request, the app surfaces were localized in Spanish and English while the project
documentation remained in English. The Decky panel now has a persistent language selector under
Settings; the Desktop Mode launcher, TUI, human-readable CLI status, and daemon warning payloads
use the configured language. JSON/RPC fields remain stable machine-facing identifiers.

An initial localization archive passed its integrity check and 77 device tests. A final incremental
archive, SHA-256 `8866ffc89ed1b9ca029393694f3ebfcb0e114d6d68829fdff4e6d354e67ecf41`, added the
remaining visible TUI action/session values and localized CLI help. It passed ZIP integrity, all 78
Python tests, the Python build, and the simulation smoke test on the Deck. Before each in-place
user-service update, configuration and data were copied coherently into the update staging area.
The final service became active with a healthy schema-3 database and mode-`0600` socket.

The six root-owned Decky files were backed up and replaced with verified source and bundle hashes
for each update; their manifest kept `flags: []`. The final `plugin_loader.service` reload logged
that SteamOS Time Guardian and its rootless bridge loaded successfully. As on the earlier reload,
Decky sent SIGKILL to its old plugin process after its five-second unload timeout and refreshed
`steamwebhelper`; no game was running or targeted. The language was then set to Spanish through
the local RPC. The human CLI status and help rendered Spanish labels and retained the weekday
45-minute/weekend 120-minute schedule, level 0, and disabled force kill. The remaining physical
check is the localized QAM panel and switching its Settings language selector back to English.

## Recovery

The owner retains physical/Desktop Mode access and SSH access. To remove the installed user
daemon and optional plugin while preserving data:

```bash
~/stg-validation-src/steamos-time-guardian/scripts/uninstall-user.sh --remove-decky
```

No uninstall, data purge, Steam restart, or forced game termination was performed in this phase.

## Notification-threshold update — 2026-07-24

The owner approved an in-place update from `main` at commit `5611e0a`, with a plugin and runtime
backup, a user-service restart, restriction level 0, force kill disabled, and no game test or
Steam/Decky restart. The target remained the same Jupiter revision-1 Deck on SteamOS 3.8.16
(build 20260716.1), kernel 6.16.12-valve24.5-1-neptune-616-gb2f7cfe85e45, Python 3.13.5, and
Decky 3.2.6. The account was `deck` (UID 1000), and `/home` had 174 GiB available.

The newly built project archive had SHA-256
`8f60e27917807ee0e7c7a1cfca6cc66ae3238db6fd424cfa6fa36fd48dbd3a70`. Its checksum and ZIP
integrity passed on the Deck before extraction. The five relevant installed Decky files
(`plugin.json`, `main.py`, `package.json`, `dist/index.js`, and `dist/index.js.map`) matched
`main` byte for byte. Because the plugin directory remains `root:root` mode `0755`, no privileged
write was justified: the adapter was left untouched and no `sudo`, Decky reload, or Steam restart
was performed. A recovery copy was retained at
`~/stg-backups/SteamOS-Time-Guardian-plugin-20260723T222715Z`.

The extracted source passed the Python-only build and simulator smoke test. The supplied
`test.sh --python-only` fallback reported zero tests because `unittest` discovery did not recurse
into the non-package `tests/unit` and `tests/integration` directories. Explicit discovery of those
two directories ran 73 unit and 14 integration tests successfully. Python 3.13 emitted repeated
`ResourceWarning` messages for log files replaced by `configure_logging`; they did not fail the
tests but remain cleanup work. A scan found no executable `steamos-readonly` or `sudo pacman`
mutation path.

Before installation, the previous user runtime, launcher, and unit were copied to
`~/stg-backups/steamos-time-guardian-runtime-20260723T222715Z`. The unprivileged installer updated
the daemon and related user files without the Decky option, preserved configuration and data, and
restarted only `steamos-time-guardian.service`. The installed `stg` tree then matched the extracted
package. In particular, `engine.py` changed from SHA-256
`7b6f9bf82cdd5366c22207cdd7befe6414fe568dc22d130f982816d9200a5c88` to
`53622953e3908e0aaeb7065cfb96cfb8fc39303082330530c9bd900985b8b82c`, matching the validated
source.

Final health checks showed the service active, database schema 3 with `quick_check: ok`, runtime
directory mode `0700`, same-UID Unix socket mode `0600`, configured and effective restriction
level 0, and force kill disabled. The Steam-log/procfs detector combination was active. The
rootless Decky bridge remained running and continued sending a recent heartbeat after two daemon
reconnections. No game was active or targeted.

The update also reproduced an unresolved shutdown defect twice. On each controlled user-service
restart, the daemon did not exit within `TimeoutStopSec=15`; systemd sent `SIGKILL` to the daemon
process and immediately started a healthy replacement. The second reproduction had no child
process and no active game, so the issue is not attributable to game enforcement. No game,
Steam, Decky, or unrelated process was killed. Graceful daemon shutdown with a live Decky bridge
must be diagnosed and fixed before claiming clean restart behavior.

The transferred archive and extracted source remain under `~/stg-update-5611e0a` and
`~/stg-validation-src-5611e0a` respectively. They, together with the two dated backups, provide a
non-destructive recovery path. No uninstall, data purge, plugin overwrite, or hardware-only UI
claim was made during this update.
