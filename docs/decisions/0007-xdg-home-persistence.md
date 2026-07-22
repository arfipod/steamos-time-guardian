# ADR 0007: Store code and data in user/XDG paths

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

Valve warns root-image changes and non-Flatpak system packages may disappear on updates. Home/XDG avoids read-only changes and supports backup/cleanup. Runtime sockets are ephemeral; config/data/state are separated.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
