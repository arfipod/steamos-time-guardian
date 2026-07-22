#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"
usage() {
  cat <<'EOF'
Usage: package.sh [--output PATH] [--skip-tests]

Builds, validates, and creates a self-contained project ZIP plus the optional Decky plugin ZIP.
EOF
}
output=""
skip_tests=0
while (($#)); do
  case "$1" in --output) shift; (($#)) || die "--output needs a path"; output="$1" ;; --skip-tests) skip_tests=1 ;; -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac
  shift
done
"$SCRIPT_DIR/build.sh"
if ((!skip_tests)); then "$SCRIPT_DIR/test.sh"; fi
mkdir -p "$PROJECT_ROOT/dist"
if [[ -z "$output" ]]; then output="$PROJECT_ROOT/dist/steamos-time-guardian-0.1.0.zip"; fi
run_python "$PROJECT_ROOT/tools/package_project.py" --project-root "$PROJECT_ROOT" --output "$output" --decky-output "$PROJECT_ROOT/dist/SteamOS-Time-Guardian-decky-0.1.0.zip"
info "Project package: $output"
info "Decky package: $PROJECT_ROOT/dist/SteamOS-Time-Guardian-decky-0.1.0.zip"
