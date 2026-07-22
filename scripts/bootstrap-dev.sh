#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: bootstrap-dev.sh [--online] [--recreate]

Creates .venv and installs the local package. With --online, also installs pinned Python developer
tools and TypeScript 5.8.3. No system packages or root privileges are used.
EOF
}

online=0
recreate=0
while (($#)); do
  case "$1" in
    --online) online=1 ;;
    --recreate) recreate=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

have python3 || die "python3 is required"
if ((recreate)); then rm -rf -- "$PROJECT_ROOT/.venv"; fi
if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  info "Creating Python virtual environment"
  python3 -m venv "$PROJECT_ROOT/.venv"
fi
info "Installing the local package without build isolation"
"$PROJECT_ROOT/.venv/bin/python" -m pip install --disable-pip-version-check --no-build-isolation --editable "$PROJECT_ROOT"

if ((online)); then
  info "Installing pinned Python developer tools"
  "$PROJECT_ROOT/.venv/bin/python" -m pip install --disable-pip-version-check --no-build-isolation --editable "$PROJECT_ROOT[dev]"
  have npm || die "npm is required to install the pinned TypeScript compiler"
  info "Installing TypeScript 5.8.3 locally for the Decky frontend"
  npm install --prefix "$PROJECT_ROOT/decky-plugin" --no-save --package-lock=false --ignore-scripts typescript@5.8.3
else
  if ! have tsc && [[ ! -x "$PROJECT_ROOT/decky-plugin/node_modules/.bin/tsc" ]]; then
    warn "TypeScript compiler unavailable; use --online before building the Decky frontend"
  fi
fi
info "Development environment ready"
