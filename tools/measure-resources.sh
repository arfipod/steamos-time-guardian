#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
usage() {
  cat <<'EOF'
Usage: measure-resources.sh [--pid PID] [--duration SECONDS] [--output FILE]

Collects CPU time, RSS, context switches, and /proc I/O for the daemon. Optional pidstat/perf data
is included when those tools are installed and permitted. It makes no system changes.
EOF
}
pid=""
duration=60
output="resource-measurement.txt"
while (($#)); do
  case "$1" in
    --pid) shift; pid=${1:-} ;;
    --duration) shift; duration=${1:-} ;;
    --output) shift; output=${1:-} ;;
    -h|--help) usage; exit 0 ;;
    *) printf '[ERROR] Unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
  shift
done
[[ "$duration" =~ ^[0-9]+$ ]] || { printf '[ERROR] duration must be numeric\n' >&2; exit 1; }
if [[ -z "$pid" ]] && command -v systemctl >/dev/null 2>&1; then
  pid="$(systemctl --user show steamos-time-guardian.service -p MainPID --value 2>/dev/null || true)"
fi
[[ "$pid" =~ ^[1-9][0-9]*$ && -d "/proc/$pid" ]] || { printf '[ERROR] daemon PID not found\n' >&2; exit 1; }
{
  printf 'timestamp=%s\npid=%s\nduration_seconds=%s\n' "$(date --iso-8601=seconds)" "$pid" "$duration"
  printf '\n[start status]\n'; grep -E '^(Name|State|VmRSS|VmHWM|Threads|voluntary_ctxt_switches|nonvoluntary_ctxt_switches):' "/proc/$pid/status" || true
  printf '\n[start io]\n'; cat "/proc/$pid/io" || true
  start_ticks="$(awk '{print $14+$15}' "/proc/$pid/stat")"
  start_read="$(awk '/read_bytes/ {print $2}' "/proc/$pid/io")"
  start_write="$(awk '/write_bytes/ {print $2}' "/proc/$pid/io")"
  if command -v pidstat >/dev/null 2>&1; then
    printf '\n[pidstat]\n'; pidstat -p "$pid" 1 "$duration" || true
  else
    sleep "$duration"
  fi
  end_ticks="$(awk '{print $14+$15}' "/proc/$pid/stat")"
  end_read="$(awk '/read_bytes/ {print $2}' "/proc/$pid/io")"
  end_write="$(awk '/write_bytes/ {print $2}' "/proc/$pid/io")"
  hz="$(getconf CLK_TCK)"
  printf '\n[delta]\ncpu_seconds=%s\nread_bytes=%s\nwrite_bytes=%s\n' \
    "$(awk -v a="$start_ticks" -v b="$end_ticks" -v h="$hz" 'BEGIN {printf "%.3f", (b-a)/h}')" \
    "$((end_read-start_read))" "$((end_write-start_write))"
  printf '\n[end status]\n'; grep -E '^(Name|State|VmRSS|VmHWM|Threads|voluntary_ctxt_switches|nonvoluntary_ctxt_switches):' "/proc/$pid/status" || true
} > "$output"
printf '[INFO] Measurement written to %s\n' "$output"
