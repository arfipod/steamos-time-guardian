#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"
usage() {
  cat <<'EOF'
Usage: diagnose.sh [--bundle PATH]

Prints live diagnostics. --bundle creates a redacted support archive without session history.
EOF
}
bundle=""
while (($#)); do
  case "$1" in --bundle) shift; (($#)) || die "--bundle needs a path"; bundle="$1" ;; -h|--help) usage; exit 0 ;; *) die "Unknown option: $1" ;; esac
  shift
done
if [[ -n "$bundle" ]]; then
  run_python "$PROJECT_ROOT/tools/support_bundle.py" --output "$bundle"
else
  run_python -m stg --json diagnose
fi
