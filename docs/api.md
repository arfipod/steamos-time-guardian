# Local IPC API

## Transport and authentication

The daemon serves newline-delimited JSON on:

```text
$XDG_RUNTIME_DIR/steamos-time-guardian/control.sock
```

Request:

```json
{"id":"client-1","method":"status.get","params":{}}
```

Success/error:

```json
{"id":"client-1","result":{}}
{"id":"client-1","error":{"code":"invalid_params","message":"..."}}
```

The socket is `0600`, directory `0700`, and Linux `SO_PEERCRED` must match daemon UID. There is no network API. Message sizes and request types are bounded in `ipc.py`.

## Public methods

| Method | Key parameters | Result |
|---|---|---|
| `service.ping` | — | version, PID |
| `status.get` / `status` | — | complete status |
| `config.get` | — | validated config |
| `config.update` | `patch` object | config, restart hint |
| `timer.start` | `seconds`, `action` | new status |
| `timer.pause` / `resume` / `cancel` | — | new status |
| `timer.adjust` | signed `seconds` | new status |
| `daily.grant` | signed `seconds`, `reason` | new status |
| `history.list` | `limit`, optional `day_key` | sessions |
| `history.events` | `limit` | events |
| `history.clear` | `PURGE_HISTORY` confirmation | cleared flag |
| `history.export` | `json`/`csv` | textual content |
| `summary.daily` | `start_day`, `days` | daily rows |
| `summary.weekly` | `end_day` | seven-day summary |
| `summary.activity` | optional `end_day`, `days` (1–90) | compact activity summary |
| `diagnostics.get` | — | redacted health snapshot |

## Adapter methods

| Method | Caller | Purpose |
|---|---|---|
| `plugin.heartbeat` | Decky | establish adapter freshness |
| `detector.report_foreground` | Decky | focused app or clear state |
| `detector.report_lifetime` | Decky | record Steam lifecycle signal |
| `enforcement.report_result` | Decky | report Steam close attempt |
| `simulation.emit` | simulator | deterministic events |

All fields have type/range/length limits. The service does not execute arbitrary commands, methods, or paths.

## Activity summary

`summary.activity` is the local data source for the controller-friendly Activity view. It returns
the selected accounting-day range, exact stored daily totals, up to three top games, recent
sessions, and a six-block (`00–04` … `20–24`) heatmap per day. It is bounded to 90 days and does
not include process IDs, paths, or other detector metadata.

The daily totals and game rankings use the retained session history, so they include history from
before this feature existed. The heatmap is deliberately different: it begins recording only after
the daemon has been upgraded to database schema 3. During normal active play, the engine derives
the blocks from matching monotonic and wall-clock intervals, keeps them in memory, and writes them
at the ordinary history checkpoint or session close. It omits uncertain intervals after suspend or
a material clock jump rather than guessing which hour was played. Consequently, a heatmap can be
partially populated while its exact totals remain complete.

`day_key` follows the configured accounting-day reset, while the block labels use the configured
time zone. This keeps the Activity view aligned with Time Guardian's daily limits, including a
non-midnight reset.

## Events

Events contain `kind`, `occurred_at`, `payload`, and `severity`. Important kinds include game/timer/daily transitions, `notification.warning`, `allowance.exhausted`, `restriction.activated`, `restriction.cleared`, enforcement results, suspend/resume, and detector errors. Clients must tolerate new kinds and fields.
