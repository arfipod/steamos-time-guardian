# Contributing

Read `AGENTS.md` and the relevant architecture decision records before changing behavior. Keep the
daemon dependency-free at runtime unless a new dependency has a measured benefit on Steam Deck.
Changes to detection or enforcement require fixtures, negative tests, documentation of failure modes,
and a safe fallback. Never claim physical Steam Deck validation without recording the exact device,
SteamOS build, client channel, Decky version, and test evidence.

Use focused commits in imperative form, for example `Fix reset boundary accounting`. Run:

```bash
./scripts/format.sh --check
./scripts/lint.sh
./scripts/test.sh
./scripts/build.sh
./scripts/smoke-test.sh
```

Security-sensitive findings should follow `SECURITY.md`, not a public issue.
