#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: install-user.sh [--with-decky] [--no-start] [--dry-run]

Installs entirely in the current user's home directory. It does not use sudo, pacman, or alter the
SteamOS read-only root. Decky is optional and is installed only with --with-decky.
EOF
}

with_decky=0
no_start=0
dry_run=0
while (($#)); do
  case "$1" in
    --with-decky) with_decky=1 ;;
    --no-start) no_start=1 ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

have python3 || die "python3 3.11 or newer is required"
python3 - <<'PY' || die "python3 3.11 or newer is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
if ((with_decky)); then
  [[ -f "$PROJECT_ROOT/decky-plugin/dist/index.js" ]] || die "Decky build output is missing; run ./scripts/build.sh first"
fi

readonly lib_dir="$HOME/.local/lib/steamos-time-guardian"
readonly bin_dir="$HOME/.local/bin"
readonly unit_dir="$HOME/.config/systemd/user"
readonly config_dir="$HOME/.config/steamos-time-guardian"
readonly data_dir="$HOME/.local/share/steamos-time-guardian"
readonly state_dir="$HOME/.local/state/steamos-time-guardian"
readonly desktop_dir="$HOME/.local/share/applications"
readonly icon_dir="$HOME/.local/share/icons/hicolor/scalable/apps"
readonly decky_root="${DECKY_HOME:-$HOME/homebrew}"
readonly decky_target="$decky_root/plugins/SteamOS-Time-Guardian"

info "Installation plan"
printf '  Runtime: %s\n  Command: %s\n  Unit: %s\n  Config: %s\n  Data: %s\n' \
  "$lib_dir" "$bin_dir/steamos-time-guardian" "$unit_dir/steamos-time-guardian.service" "$config_dir" "$data_dir"
if ((with_decky)); then printf '  Decky plugin: %s\n' "$decky_target"; else printf '  Decky plugin: not requested\n'; fi
if ((dry_run)); then exit 0; fi

if ((with_decky)) && [[ ! -d "$decky_root/plugins" ]]; then
  die "Decky plugin directory not found at $decky_root/plugins; install/verify Decky first or omit --with-decky"
fi

stage="$(mktemp -d "${TMPDIR:-/tmp}/stg-install.XXXXXX")"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
declare -a installed=()
declare -a backup_targets=()
declare -a backup_paths=()
was_active=0
systemd_available=0
committed=0

cleanup() { rm -rf -- "$stage"; }
rollback() {
  local status=$?
  if ((committed)); then cleanup; return "$status"; fi
  warn "Installation failed; rolling back program files"
  for target in "${installed[@]}"; do rm -rf -- "$target"; done
  local index
  for ((index=${#backup_targets[@]}-1; index>=0; index--)); do
    if [[ -e "${backup_paths[$index]}" || -L "${backup_paths[$index]}" ]]; then
      mkdir -p -- "$(dirname -- "${backup_targets[$index]}")"
      mv -- "${backup_paths[$index]}" "${backup_targets[$index]}"
    fi
  done
  if ((systemd_available)); then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    if ((was_active)); then systemctl --user start steamos-time-guardian.service >/dev/null 2>&1 || true; fi
  fi
  cleanup
  exit "$status"
}
trap rollback ERR INT TERM

mkdir -p "$stage/lib" "$stage/bin" "$stage/unit" "$stage/desktop" "$stage/icon"
cp -a "$PROJECT_ROOT/daemon/src/stg" "$stage/lib/stg"
cp -a "$PROJECT_ROOT/docs" "$stage/lib/docs"
cp "$PROJECT_ROOT/README.md" "$PROJECT_ROOT/LICENSE" "$PROJECT_ROOT/CHANGELOG.md" "$stage/lib/"
sed "s|@LIB_DIR@|$lib_dir|g" "$PROJECT_ROOT/packaging/steamos-time-guardian" > "$stage/bin/steamos-time-guardian"
chmod 0755 "$stage/bin/steamos-time-guardian"
cp "$PROJECT_ROOT/systemd/steamos-time-guardian.service" "$stage/unit/"
cp "$PROJECT_ROOT/desktop-ui/steamos-time-guardian.desktop" "$stage/desktop/"
cp "$PROJECT_ROOT/desktop-ui/steamos-time-guardian.svg" "$stage/icon/"
if ((with_decky)); then
  mkdir -p "$stage/decky/dist"
  cp "$PROJECT_ROOT/decky-plugin/dist/index.js" "$PROJECT_ROOT/decky-plugin/dist/index.js.map" "$stage/decky/dist/"
  cp "$PROJECT_ROOT/decky-plugin/main.py" "$PROJECT_ROOT/decky-plugin/plugin.json" \
    "$PROJECT_ROOT/decky-plugin/package.json" "$PROJECT_ROOT/decky-plugin/LICENSE" "$stage/decky/"
fi

replace_path() {
  local source=$1 target=$2 backup
  mkdir -p -- "$(dirname -- "$target")"
  if [[ -e "$target" || -L "$target" ]]; then
    backup="${target}.backup-${stamp}"
    rm -rf -- "$backup"
    mv -- "$target" "$backup"
    backup_targets+=("$target")
    backup_paths+=("$backup")
  fi
  mv -- "$source" "$target"
  installed+=("$target")
}

if have systemctl && systemctl --user show-environment >/dev/null 2>&1; then
  systemd_available=1
  if systemctl --user is-active --quiet steamos-time-guardian.service; then
    was_active=1
    systemctl --user stop steamos-time-guardian.service
  fi
fi

replace_path "$stage/lib" "$lib_dir"
replace_path "$stage/bin/steamos-time-guardian" "$bin_dir/steamos-time-guardian"
replace_path "$stage/unit/steamos-time-guardian.service" "$unit_dir/steamos-time-guardian.service"
replace_path "$stage/desktop/steamos-time-guardian.desktop" "$desktop_dir/steamos-time-guardian.desktop"
replace_path "$stage/icon/steamos-time-guardian.svg" "$icon_dir/steamos-time-guardian.svg"
if ((with_decky)); then replace_path "$stage/decky" "$decky_target"; fi

mkdir -p -m 0700 "$config_dir" "$data_dir" "$state_dir"
if [[ ! -f "$config_dir/config.json" ]]; then
  cp "$PROJECT_ROOT/config/config.example.json" "$config_dir/config.json"
  chmod 0600 "$config_dir/config.json"
  info "Installed default configuration"
else
  info "Preserved existing configuration"
fi

if ((systemd_available)); then
  systemctl --user daemon-reload
  systemctl --user enable steamos-time-guardian.service >/dev/null
  if ((!no_start)); then
    systemctl --user restart steamos-time-guardian.service
    systemctl --user is-active --quiet steamos-time-guardian.service || die "service did not become active"
  fi
else
  warn "No reachable systemd user manager; run '$bin_dir/steamos-time-guardian daemon' manually"
fi

committed=1
trap - ERR INT TERM
cleanup
for backup in "${backup_paths[@]}"; do rm -rf -- "$backup"; done
info "Installation completed"
service_started="no"
if ((systemd_available && !no_start)); then service_started="yes"; fi
printf '  Command: %s\n  Service started: %s\n  Data retained across updates: %s\n' \
  "$bin_dir/steamos-time-guardian" "$service_started" "$data_dir"
if ((with_decky)); then
  warn "Decky plugin files were installed. Reload plugins or restart the Steam client from its UI; this script does not restart Steam."
else
  info "Game Mode integration was not installed; Desktop CLI/TUI and daemon remain fully usable."
fi
