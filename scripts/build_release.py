#!/usr/bin/env python3
"""
Build a standalone executable for the current platform with PyInstaller.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PROJECT_ROOT / "qq_map_cli.py"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_DIR = BUILD_DIR / "spec"
PYINSTALLER_CONFIG_DIR = BUILD_DIR / "pyinstaller-cache"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
APP_NAME = "qq-map-cli"


def platform_label() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    machine = aliases.get(machine, machine)
    return f"{system}-{machine}"


def run(cmd: list[str]) -> None:
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(PYINSTALLER_CONFIG_DIR)
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, env=env)


def build(onefile: bool, clean: bool) -> Path:
    if clean:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller-work"),
        "--specpath",
        str(SPEC_DIR),
        "--name",
        APP_NAME,
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd.append(str(ENTRYPOINT))
    run(cmd)

    if onefile:
        suffix = ".exe" if os.name == "nt" else ""
        return DIST_DIR / f"{APP_NAME}{suffix}"
    return DIST_DIR / APP_NAME


def make_archive(target: Path, onefile: bool) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    archive_base = ARTIFACTS_DIR / f"{APP_NAME}-{platform_label()}"
    if not onefile:
        archive_base = ARTIFACTS_DIR / f"{APP_NAME}-{platform_label()}-dir"

    if archive_base.with_suffix(".zip").exists():
        archive_base.with_suffix(".zip").unlink()

    if target.is_dir():
        return Path(shutil.make_archive(str(archive_base), "zip", root_dir=target.parent, base_dir=target.name))

    staging_dir = BUILD_DIR / "archive-staging"
    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, staging_dir / target.name)
    return Path(shutil.make_archive(str(archive_base), "zip", root_dir=staging_dir, base_dir="."))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standalone release artifacts.")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build a one-directory bundle instead of a one-file executable.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Keep previous build and dist directories.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = build(onefile=not args.onedir, clean=not args.no_clean)
    archive = make_archive(target, onefile=not args.onedir)
    print(f"built_target: {target}")
    print(f"archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
