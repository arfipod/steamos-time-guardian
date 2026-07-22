#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"
usage() { printf 'Usage: status.sh [--json]\n'; }
json=0
while (($#)); do case "$1" in --json) json=1 ;; -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac; shift; done
if have systemctl; then
  systemctl --user --no-pager --full status steamos-time-guardian.service || true
fi
args=(status)
if ((json)); then args=(--json status); fi
if [[ -x "$HOME/.local/bin/steamos-time-guardian" ]]; then
  "$HOME/.local/bin/steamos-time-guardian" "${args[@]}"
else
  run_python -m stg "${args[@]}"
fi
