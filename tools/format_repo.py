#!/usr/bin/env python3
"""Normalize text files without requiring a formatter dependency."""

from __future__ import annotations

import argparse
from pathlib import Path

TEXT_SUFFIXES = {".py", ".pyi", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".toml", ".yml", ".yaml", ".sh", ".service", ".desktop", ".svg"}
SKIP_PARTS = {".git", ".venv", ".dev", "node_modules", "__pycache__", "dist", "build"}


def candidates(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Makefile", "LICENSE"}:
            yield path


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    changed: list[Path] = []
    for path in candidates(args.root):
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        formatted = normalize(original)
        if original != formatted:
            changed.append(path.relative_to(args.root))
            if not args.check:
                path.write_text(formatted, encoding="utf-8")
    if changed:
        prefix = "would reformat" if args.check else "reformatted"
        for path in changed:
            print(f"{prefix}: {path}")
        return 1 if args.check else 0
    print("text formatting check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
