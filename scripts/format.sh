#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() { printf 'Usage: format.sh [--check]\n'; }
check=0
while (($#)); do
  case "$1" in --check) check=1 ;; -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac
  shift
done
python="$(python_bin)"
if "$python" -c 'import ruff' >/dev/null 2>&1; then
  if ((check)); then
    (cd "$PROJECT_ROOT" && "$python" -m ruff format --check daemon/src tests tools)
  else
    (cd "$PROJECT_ROOT" && "$python" -m ruff format daemon/src tests tools)
  fi
fi
if ((check)); then
  run_python "$PROJECT_ROOT/tools/format_repo.py" --check
else
  run_python "$PROJECT_ROOT/tools/format_repo.py"
fi
