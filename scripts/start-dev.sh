#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: start-dev.sh [--reset]

Runs the daemon in simulation mode with all XDG data isolated under .dev/.
EOF
}
reset=0
while (($#)); do
  case "$1" in --reset) reset=1 ;; -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac
  shift
done
if ((reset)); then rm -rf -- "$PROJECT_ROOT/.dev"; fi
mkdir -p "$PROJECT_ROOT/.dev"/{config,data,state,runtime}
export XDG_CONFIG_HOME="$PROJECT_ROOT/.dev/config"
export XDG_DATA_HOME="$PROJECT_ROOT/.dev/data"
export XDG_STATE_HOME="$PROJECT_ROOT/.dev/state"
export XDG_RUNTIME_DIR="$PROJECT_ROOT/.dev/runtime"
export STG_SIMULATION=1
info "Starting simulation daemon; use another terminal for CLI commands"
exec env PYTHONPATH="$PROJECT_ROOT/daemon/src${PYTHONPATH:+:$PYTHONPATH}" "$(python_bin)" -m stg daemon --simulation
