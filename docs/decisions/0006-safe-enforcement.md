# ADR 0006: Use cooperative isolated enforcement

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

Levels 0–1 never terminate processes. Levels 2–3 request Steam close after grace, then optionally signal only verified same-UID matching-App-ID PIDs. SIGKILL is opt-in. No launch wrappers, root policy, library modification, or Desktop lock is used.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
