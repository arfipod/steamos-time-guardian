#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: build.sh [--python-only] [--decky-only]

Compiles Python bytecode and/or the optional Decky TypeScript frontend.
EOF
}

python_build=1
decky_build=1
while (($#)); do
  case "$1" in
    --python-only) decky_build=0 ;;
    --decky-only) python_build=0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

if ((python_build)); then
  info "Compiling Python sources"
  run_python -m compileall -q -f "$PROJECT_ROOT/daemon/src" "$PROJECT_ROOT/tools"
fi
if ((decky_build)); then
  have node || die "Node.js 22 is required to build the Decky frontend"
  info "Building Decky frontend"
  (cd "$PROJECT_ROOT/decky-plugin" && node scripts/build.mjs)
  run_python -m py_compile "$PROJECT_ROOT/decky-plugin/main.py"
fi
info "Build completed"
