#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: test.sh [--coverage] [--python-only] [--plugin-only]
EOF
}

coverage=0
python_tests=1
plugin_tests=1
while (($#)); do
  case "$1" in
    --coverage) coverage=1 ;;
    --python-only) plugin_tests=0 ;;
    --plugin-only) python_tests=0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

if ((python_tests)); then
  python="$(python_bin)"
  if ((coverage)) && "$python" -c 'import pytest, pytest_cov' >/dev/null 2>&1; then
    info "Running Python tests with pytest coverage"
    (cd "$PROJECT_ROOT" && PYTHONPATH=daemon/src "$python" -m pytest tests \
      --cov=stg --cov-branch --cov-report=term-missing)
  elif ((coverage)) && "$python" -c 'import coverage' >/dev/null 2>&1; then
    info "Running Python tests with coverage and unittest discovery"
    PYTHONPATH="$PROJECT_ROOT/daemon/src" "$python" -m coverage run -m unittest discover -s "$PROJECT_ROOT/tests" -t "$PROJECT_ROOT" -p 'test_*.py' -v
    PYTHONPATH="$PROJECT_ROOT/daemon/src" "$python" -m coverage report
  elif "$python" -c 'import pytest' >/dev/null 2>&1; then
    info "Running Python tests with pytest"
    PYTHONPATH="$PROJECT_ROOT/daemon/src" "$python" -m pytest "$PROJECT_ROOT/tests"
  else
    info "Running Python tests with unittest"
    PYTHONPATH="$PROJECT_ROOT/daemon/src" "$python" -m unittest discover -s "$PROJECT_ROOT/tests" -t "$PROJECT_ROOT" -v
  fi
fi
if ((plugin_tests)); then
  info "Running Decky build and smoke test"
  (cd "$PROJECT_ROOT/decky-plugin" && npm test)
fi
info "All requested tests passed"
