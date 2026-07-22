#!/usr/bin/env python3
"""Create deterministic project and Decky ZIP archives and verify their contents."""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".dev",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "htmlcov",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {".coverage", ".DS_Store"}
REQUIRED_ARCHIVE_FILES = {
    "README.md",
    "AGENTS.md",
    "daemon/src/stg/service.py",
    "decky-plugin/dist/index.js",
    "scripts/install-user.sh",
    "scripts/uninstall-user.sh",
    "docs/architecture.md",
    "docs/local-validation-report.md",
    "docs/sources.md",
    "docs/steam-deck-validation-plan.md",
    ".github/workflows/ci.yml",
}
TIMESTAMP = (2026, 7, 22, 0, 0, 0)


def include(path: Path, root: Path, outputs: set[Path]) -> bool:
    if path.resolve() in outputs:
        return False
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.parts and relative.parts[0] == "dist":
        return False
    if path.name in EXCLUDED_NAMES or any(part.endswith(".egg-info") for part in relative.parts):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES and not path.name.endswith("~")


def add_file(archive: zipfile.ZipFile, source: Path, archive_name: str) -> None:
    info = zipfile.ZipInfo(archive_name, TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = source.stat().st_mode & 0o777
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, source.read_bytes())


def build_project(root: Path, output: Path, outputs: set[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    prefix = "steamos-time-guardian"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and include(path, root, outputs):
                add_file(archive, path, f"{prefix}/{path.relative_to(root).as_posix()}")
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        missing = {f"{prefix}/{item}" for item in REQUIRED_ARCHIVE_FILES} - names
        if missing:
            raise RuntimeError(f"project archive is missing: {sorted(missing)}")
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"corrupt member in project archive: {bad}")


def build_decky(root: Path, output: Path) -> None:
    plugin = root / "decky-plugin"
    required = [
        plugin / "dist/index.js",
        plugin / "dist/index.js.map",
        plugin / "main.py",
        plugin / "plugin.json",
        plugin / "package.json",
        plugin / "LICENSE",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Decky package inputs missing: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    prefix = "SteamOS-Time-Guardian"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in required:
            add_file(archive, path, f"{prefix}/{path.relative_to(plugin).as_posix()}")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise RuntimeError("Decky archive verification failed")


def write_digest(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decky-output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    outputs = {args.output.resolve(), args.decky_output.resolve()}
    build_project(root, args.output.resolve(), outputs)
    build_decky(root, args.decky_output.resolve())
    write_digest(args.output.resolve())
    write_digest(args.decky_output.resolve())
    print(f"created {args.output} ({args.output.stat().st_size} bytes)")
    print(f"created {args.decky_output} ({args.decky_output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
