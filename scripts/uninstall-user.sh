#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: uninstall-user.sh [--remove-decky] [--purge-data --yes]

Removes installed program files. Configuration, history, and logs are retained by default.
--purge-data permanently deletes them and requires --yes.
EOF
}
remove_decky=0
purge=0
yes=0
while (($#)); do
  case "$1" in
    --remove-decky) remove_decky=1 ;;
    --purge-data) purge=1 ;;
    --yes) yes=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done
if ((purge && !yes)); then die "--purge-data is destructive and requires --yes"; fi

lib_dir="$HOME/.local/lib/steamos-time-guardian"
bin_file="$HOME/.local/bin/steamos-time-guardian"
unit_file="$HOME/.config/systemd/user/steamos-time-guardian.service"
config_dir="$HOME/.config/steamos-time-guardian"
data_dir="$HOME/.local/share/steamos-time-guardian"
state_dir="$HOME/.local/state/steamos-time-guardian"
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  runtime_dir="$XDG_RUNTIME_DIR/steamos-time-guardian"
else
  runtime_dir="/tmp/steamos-time-guardian-$UID"
fi
desktop_file="$HOME/.local/share/applications/steamos-time-guardian.desktop"
icon_file="$HOME/.local/share/icons/hicolor/scalable/apps/steamos-time-guardian.svg"
decky_target="${DECKY_HOME:-$HOME/homebrew}/plugins/SteamOS-Time-Guardian"

if have systemctl && systemctl --user show-environment >/dev/null 2>&1; then
  systemctl --user disable --now steamos-time-guardian.service >/dev/null 2>&1 || true
fi
rm -rf -- "$lib_dir"
rm -f -- "$bin_file" "$unit_file" "$desktop_file" "$icon_file"
if have systemctl && systemctl --user show-environment >/dev/null 2>&1; then systemctl --user daemon-reload; fi
if ((remove_decky)); then rm -rf -- "$decky_target"; fi
if ((purge)); then
  info "Purging configuration, database, logs, and runtime files"
  rm -rf -- "$config_dir" "$data_dir" "$state_dir" "$runtime_dir"
else
  info "Preserved configuration and data"
  printf '  Config: %s\n  Data: %s\n  Logs: %s\n' "$config_dir" "$data_dir" "$state_dir"
fi
info "Uninstallation completed"
