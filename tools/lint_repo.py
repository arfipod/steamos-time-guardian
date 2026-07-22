#!/usr/bin/env python3
"""Offline repository integrity and safety lint."""

from __future__ import annotations

import ast
import json
import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", ".dev", "node_modules", "__pycache__", "build", "dist"}
REQUIRED = {
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "Makefile",
    "pyproject.toml",
    "config/config.example.json",
    "config/schema.json",
    "systemd/steamos-time-guardian.service",
    "decky-plugin/plugin.json",
    "decky-plugin/main.py",
    "decky-plugin/dist/index.js",
    "docs/architecture.md",
    "docs/sources.md",
    "docs/steam-deck-validation-plan.md",
}
REQUIRED_SCRIPTS = {
    "bootstrap-dev.sh",
    "build.sh",
    "test.sh",
    "lint.sh",
    "format.sh",
    "install-user.sh",
    "uninstall-user.sh",
    "start-dev.sh",
    "status.sh",
    "diagnose.sh",
    "package.sh",
    "smoke-test.sh",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


def files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not any(part in SKIP for part in path.relative_to(ROOT).parts):
            yield path


def main() -> int:
    errors: list[str] = []
    for relative in sorted(REQUIRED):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    for name in sorted(REQUIRED_SCRIPTS):
        path = ROOT / "scripts" / name
        if not path.is_file():
            errors.append(f"missing required script: scripts/{name}")
            continue
        mode = path.stat().st_mode
        if not mode & stat.S_IXUSR:
            errors.append(f"script is not executable: scripts/{name}")
        first_lines = path.read_text(encoding="utf-8").splitlines()[:8]
        if not first_lines or not first_lines[0].startswith("#!"):
            errors.append(f"script lacks shebang: scripts/{name}")
        if not any("set -euo pipefail" in line for line in first_lines):
            errors.append(f"script lacks strict mode near top: scripts/{name}")

    sandbox_prefix = "/" + "mnt/data/"
    for path in files():
        relative = path.relative_to(ROOT)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if sandbox_prefix in content or str(ROOT) in content:
            errors.append(f"environment-specific absolute path in {relative}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                errors.append(f"possible secret in {relative}")
        if path.suffix == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {relative}: {exc}")
        if path.suffix == ".py":
            try:
                tree = ast.parse(content, filename=str(relative))
            except SyntaxError as exc:
                errors.append(f"invalid Python in {relative}: {exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                        errors.append(f"os.system is forbidden in {relative}:{node.lineno}")
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            errors.append(f"shell=True is forbidden in {relative}:{node.lineno}")

    plugin = json.loads((ROOT / "decky-plugin/plugin.json").read_text(encoding="utf-8"))
    flags = set(plugin.get("flags", []))
    if "root" in flags or "_root" in flags:
        errors.append("Decky plugin must remain rootless")
    unit = (ROOT / "systemd/steamos-time-guardian.service").read_text(encoding="utf-8")
    if "NoNewPrivileges=yes" not in unit or "ExecStart=%h/.local/bin/steamos-time-guardian" not in unit:
        errors.append("systemd unit is missing expected user-service hardening")
    config = json.loads((ROOT / "config/config.example.json").read_text(encoding="utf-8"))
    if config["restriction"]["force_kill_enabled"] is not False or config["restriction"]["level"] != 0:
        errors.append("safe default restriction settings changed")

    if errors:
        print("Repository lint failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"repository lint passed ({sum(1 for _ in files())} checked files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
