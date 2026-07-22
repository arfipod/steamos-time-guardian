#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"
usage() { printf 'Usage: smoke-test.sh\n'; }
if (($#)); then case "$1" in -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac; fi

work="$(mktemp -d "${TMPDIR:-/tmp}/stg-smoke.XXXXXX")"
pid=""
cleanup() {
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  rm -rf -- "$work"
}
trap cleanup EXIT INT TERM
mkdir -p "$work"/{config,data,state,runtime}
export XDG_CONFIG_HOME="$work/config"
export XDG_DATA_HOME="$work/data"
export XDG_STATE_HOME="$work/state"
export XDG_RUNTIME_DIR="$work/runtime"
export STG_SIMULATION=1
python="$(python_bin)"
export PYTHONPATH="$PROJECT_ROOT/daemon/src${PYTHONPATH:+:$PYTHONPATH}"
"$python" -m stg daemon --simulation --no-foreground-log >"$work/daemon.out" 2>"$work/daemon.err" &
pid=$!
socket="$XDG_RUNTIME_DIR/steamos-time-guardian/control.sock"
for _ in {1..100}; do [[ -S "$socket" ]] && break; sleep 0.05; done
[[ -S "$socket" ]] || { cat "$work/daemon.err" >&2; die "daemon socket was not created"; }
"$python" -m stg --json config patch '{"warnings":{"native_desktop_notifications":false},"history":{"checkpoint_seconds":5}}' >/dev/null
"$python" -m stg --json simulate game_started --app-id 424242 --name 'Smoke Game' >/dev/null
"$python" -m stg --json timer start 1m >/dev/null
"$python" -m stg --json simulate suspend >/dev/null
"$python" -m stg --json simulate resume >/dev/null
"$python" -m stg --json status >"$work/status.json"
"$python" - "$work/status.json" <<'PY'
import json, sys
status=json.load(open(sys.argv[1], encoding='utf-8'))
assert status['game']['app_id']=='424242', status
assert status['timer']['state']=='running', status
assert status['suspended'] is False, status
PY
"$python" -m stg --json simulate game_stopped >/dev/null
"$python" -m stg --json history list --limit 10 >"$work/history.json"
"$python" - "$work/history.json" <<'PY'
import json, sys
history=json.load(open(sys.argv[1], encoding='utf-8'))
assert any(item['app_id']=='424242' for item in history['sessions']), history
PY
"$python" -m stg --json diagnose >"$work/diagnostics.json"
"$python" - "$work/diagnostics.json" <<'PY'
import json, sys
data=json.load(open(sys.argv[1], encoding='utf-8'))
assert data['database']['quick_check']=='ok', data
assert data['database']['schema_version']==3, data
PY
info "Simulation smoke test passed"
