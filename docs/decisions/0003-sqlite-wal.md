# ADR 0003: Use SQLite with WAL for local persistence

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

SQLite is standard-library accessible, transactional, crash-resistant, and queryable. WAL supports concurrent reads with one serialized writer; periodic checkpoints avoid per-second writes. Flat JSON cannot safely enforce one open session or summarize history; a server database is disproportionate.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
