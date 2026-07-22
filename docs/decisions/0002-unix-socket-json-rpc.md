# ADR 0002: Use same-user JSON RPC over a Unix socket

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

A Unix socket in XDG runtime avoids a network surface, supports filesystem modes and Linux SO_PEERCRED, and needs no HTTP framework or D-Bus code generation. Newline JSON is inspectable/versionable. D-Bus remains useful for notifications but is unnecessary for core IPC.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
