# ADR 0001: Use Python for the user service

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

Python 3.11+ provides asyncio, sqlite3, Unix sockets, zoneinfo, logging, and monotonic clocks in the standard library. A dependency-free runtime reduces installation risk on an immutable OS. Rust/Go could reduce RSS/startup but add cross-compilation and binary compatibility work before hardware measurements. Revisit only if measured resource use misses targets.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
