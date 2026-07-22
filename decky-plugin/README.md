# SteamOS Time Guardian — Decky UI

Optional, rootless Quick Access Menu frontend. It contains no tracking database and is safe to
remove independently: the user daemon continues tracking and the Desktop Mode CLI/TUI remains
available.

The frontend uses Decky's current plugin runtime contract and wraps access to Steam UI objects in
one file. `SteamClient.GameSessions.RegisterForAppLifetimeNotifications`,
`DFL.Router.MainRunningApp`, and `SteamClient.Apps.TerminateApp` are treated as compatibility
adapters because they are not stable public Valve APIs.

Build with `npm run build`. The project has no runtime or npm package dependencies; it requires the
pinned TypeScript 5.8.x compiler supplied by `scripts/bootstrap-dev.sh --online` or CI.
