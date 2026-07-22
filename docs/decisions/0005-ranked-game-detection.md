# ADR 0005: Combine ranked detector sources

- Status: **Accepted**
- Date: 2026-07-22

## Context

SteamOS Time Guardian must meet Steam Deck integration, persistence, low-resource, safety, and maintainability constraints without physical hardware in the first phase.

## Decision

No stable public unprivileged game-foreground API was found. Decky focus/lifetime has highest confidence, Steam process log supplies event-driven App ID/PID tracking, and procfs environment scanning is a slow fallback. Process names alone are rejected; ambiguous non-Steam/emulator cases undercount rather than enforce.

## Consequences

The approach is implemented and tested in simulation. Compatibility-sensitive assumptions remain isolated and require hardware validation before stronger enforcement. Reversal requires a superseding ADR, migration/rollback plan, and security analysis.
