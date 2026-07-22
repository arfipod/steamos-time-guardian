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

## Events

Events contain `kind`, `occurred_at`, `payload`, and `severity`. Important kinds include game/timer/daily transitions, `notification.warning`, `allowance.exhausted`, `restriction.activated`, `restriction.cleared`, enforcement results, suspend/resume, and detector errors. Clients must tolerate new kinds and fields.
