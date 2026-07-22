# ADR 0004: Use Decky as an optional Game Mode adapter

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

Decky provides practical QAM integration, toasts, focused-app state, and Steam close compatibility. It is third-party and update-sensitive, so it must not own accounting or data. The daemon/Desktop UI remain independent. The plugin uses no root flag and installation is explicit.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
