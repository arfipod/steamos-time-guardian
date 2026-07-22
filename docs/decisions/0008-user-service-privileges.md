# ADR 0008: Run as a hardened systemd user service

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

The application needs supervision across Steam client restarts but not root. systemd --user provides restart and journal integration. The unit denies privilege escalation and grants writes only to application XDG/runtime paths. A system service/root Decky backend would expand impact.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
