# Security policy

## Supported versions

The `0.1.x` line receives security fixes while it remains the current development line.

## Reporting

Do not publish details that could cause arbitrary process termination, socket authorization bypass,
path traversal, or unsafe command execution. Share a minimal reproduction privately with the project
maintainer responsible for the deployment. This source archive contains no contact endpoint; establish
one before public distribution.

## Security boundaries

- The daemon and Decky backend run as the normal SteamOS user.
- IPC is a mode-`0600` Unix socket and verifies Linux `SO_PEERCRED` UID.
- No network listener, telemetry, remote account, secret, or shell-built command is used.
- Process termination is isolated, same-UID checked, App-ID checked, protected-process filtered, and
  disabled at the forced level by default.
- A device owner with shell or administrative access can bypass any local restriction. This project is
  a time-management aid, not tamper-proof parental-control infrastructure.

See `docs/security-model.md` for the complete threat model.
