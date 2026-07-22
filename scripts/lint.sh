#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() { printf 'Usage: lint.sh\n'; }
if (($#)); then
  case "$1" in -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac
fi

info "Running repository integrity lint"
run_python "$PROJECT_ROOT/tools/lint_repo.py"
info "Checking shell syntax"
while IFS= read -r -d '' script; do bash -n "$script"; done < <(find "$PROJECT_ROOT/scripts" "$PROJECT_ROOT/tools" -type f -name '*.sh' -print0)
python="$(python_bin)"
if "$python" -c 'import ruff' >/dev/null 2>&1; then
  info "Running Ruff"
  (cd "$PROJECT_ROOT" && "$python" -m ruff check .)
else
  warn "Ruff not installed; structural lint and Python compilation still ran"
fi
if "$python" -c 'import mypy' >/dev/null 2>&1; then
  info "Running mypy"
  (cd "$PROJECT_ROOT" && PYTHONPATH=daemon/src "$python" -m mypy daemon/src/stg)
else
  warn "mypy not installed; runtime type-sensitive tests still ran"
fi
info "Type-checking Decky frontend"
(cd "$PROJECT_ROOT/decky-plugin" && node scripts/build.mjs --check)
info "Lint completed"
