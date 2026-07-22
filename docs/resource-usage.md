# Resource usage and measurement

## Design targets

- Idle CPU close to measurement noise.
- No per-second polling.
- Five-second accounting wake while active; 30-second idle wake.
- Linux inotify for Steam log changes, with a long safety timeout.
- Procfs fallback every 15 seconds by default, same-user only.
- SQLite checkpoints every 30 seconds by default, not every tick.
- No permanent overlay process outside the existing Decky panel.
- No network activity or telemetry.

The Python daemon keeps one SQLite connection, one socket server, detector tasks, and small state. Actual Steam Deck values must be measured; no battery-impact claim is made from simulation.

## Conventional Linux measurement

```bash
./scripts/start-dev.sh --reset
pgrep -af 'stg daemon'
./tools/measure-resources.sh --pid <PID> --duration 60
```

Compare idle, active simulation, notification, and export scenarios.

## Steam Deck commands

Do not install packages on the immutable root just for measurement.

```bash
systemctl --user show steamos-time-guardian.service \
  -p MainPID -p MemoryCurrent -p CPUUsageNSec -p TasksCurrent
pid=$(systemctl --user show -p MainPID --value steamos-time-guardian.service)
ps -p "$pid" -o pid,etimes,%cpu,rss,vsz,nlwp,cmd
cat "/proc/$pid/io"
cat "/proc/$pid/status"
```

When `powertop` already exists, root-level measurement still requires explicit approval:

```bash
sudo powertop --time=60 --html="$HOME/stg-powertop.html"
```

Non-root systemd CPU delta:

```bash
before=$(systemctl --user show -p CPUUsageNSec --value steamos-time-guardian.service)
sleep 300
after=$(systemctl --user show -p CPUUsageNSec --value steamos-time-guardian.service)
python3 -c "print((int('$after')-int('$before'))/1e9, 'CPU seconds / 300 wall seconds')"
```

Disk and memory trends:

```bash
cat "/proc/$pid/io"; sleep 300; cat "/proc/$pid/io"
for i in {1..12}; do date -Is; awk '/VmRSS|VmHWM|Threads/ {print}' "/proc/$pid/status"; sleep 300; done
```

## Test matrix

1. Idle, no Decky.
2. Idle, Decky connected/QAM closed.
3. Game active for 30 minutes.
4. QAM opened/closed repeatedly.
5. All warning thresholds.
6. Suspend 15 minutes/resume.
7. Steam log rotation.
8. Decky disconnected/fallback detector.
9. History export/support bundle.
10. 24-hour soak/daily reset.

Record Deck model, SteamOS/Decky versions, battery policy, game, TDP/frame cap, external power, and screen state.

## Provisional acceptance targets

These are targets, not measured results: idle average CPU below 0.2%, RSS below 60 MiB, no rapid memory growth, no writes every second, and no observable resume/frame-time delay. Revise only after evidence.
