#!/usr/bin/env python3
"""Bundle the complete prepared MAME sources and this port's build materials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from package_archive import package_archive, sha256
from generate_rom_patch_header import load_patch_module, render


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_ROOTS = {
    ".git", "build", "out", "roms", ".private-roms", "sessions", "session",
    "cfg", "nvram", "test-results", "snap", "snapshots", "saves", "states",
}


def git(tree: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(tree), *args], text=True).strip()


def copy_checkout(tree: Path, destination: Path) -> int:
    # --exclude-standard affects only --others: upstream's broad .gitignore
    # must never remove tracked sources (including third-party dependencies).
    paths = subprocess.check_output([
        "git", "-C", str(tree), "ls-files", "-z", "--cached", "--others",
        "--exclude-standard",
    ]).split(b"\0")
    copied = 0
    for raw in sorted(set(paths)):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.parts[0] in EXCLUDED_ROOTS or ".git" in relative.parts:
            continue
        if relative.suffix.lower() in {".smp", ".gen"}:
            continue
        source, target = tree / relative, destination / relative
        if not source.exists() and not source.is_symlink():
            continue  # A tracked file deleted in the prepared working tree.
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"Unsupported source entry (submodule?): {source}")
        copied += 1
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mame_tree", type=Path)
    args = parser.parse_args()
    mame = args.mame_tree.resolve()
    version = os.environ.get("PACKAGE_VERSION", (ROOT / "VERSION").read_text().strip())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise RuntimeError(f"Invalid package version: {version}")
    expected = (ROOT / "MAME_COMMIT").read_text().strip()
    if git(mame, "rev-parse", "HEAD") != expected:
        raise RuntimeError("The prepared MAME checkout does not match MAME_COMMIT.")
    subprocess.run([
        "git", "-C", str(mame), "apply", "--reverse", "--check",
        str(ROOT / "patches/mame0289-space-harrier-mdp.patch"),
    ], check=True)
    header = mame / "src/devices/bus/megadrive/sh1_mdp_rom.h"
    if not header.is_file():
        raise RuntimeError("The prepared MAME checkout lacks its generated ROM adapter.")
    if header.read_text(encoding="utf-8") != render(load_patch_module(ROOT / "rompatch/patch.py")):
        raise RuntimeError("The prepared MAME checkout has a stale generated ROM adapter.")
    if not (ROOT / "CHANGELOG.md").is_file():
        raise RuntimeError("CHANGELOG.md is required in release packages.")
    output = Path(os.environ.get("PACKAGE_OUTPUT_DIR", str(ROOT / "out"))).resolve()
    package = output / f"space-harrier-mdp-{version}-source"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    counts = {
        "port": copy_checkout(ROOT, package / "space-harrier-mdp-libretro"),
        "mame": copy_checkout(mame, package / "libretro-mame"),
    }
    shutil.copy2(ROOT / "CHANGELOG.md", package / "CHANGELOG.md")
    (package / "BUILD.json").write_text(json.dumps({
        "schema_version": 1,
        "kind": "source",
        "platform": "source",
        "package_version": version,
        "source_commit": git(ROOT, "rev-parse", "HEAD"),
        "source_tree_dirty": bool(git(ROOT, "status", "--porcelain")),
        "mame_commit": expected,
        "mame_tree_dirty": bool(git(mame, "status", "--porcelain")),
        "source_file_counts": counts,
        "rom_patch_table_sha256": sha256(ROOT / "rompatch/patch.py"),
        "generated_rom_adapter_sha256": sha256(header),
    }, indent=2) + "\n", encoding="utf-8")
    (package / "BUILDING.txt").write_text(
        "Complete corresponding source for Space Harrier MDP.\n\n"
        "libretro-mame contains the full pinned upstream source tree with the\n"
        "MDP patch and generated ROM adapter already applied. The port directory\n"
        "contains the build scripts, Windows portability patch, tests, licences\n"
        "and build dependency instructions. No ROM, Git database or build output\n"
        "is included. Files ignored by upstream Git are not used to filter its\n"
        "tracked source files.\n\n"
        "From space-harrier-mdp-libretro, follow README.md for dependencies, then\n"
        "run: ./scripts/build-libretro.sh ../libretro-mame\n"
        "On Windows use an MSYS2 MinGW64 shell with PLATFORM=win; on macOS use\n"
        "PLATFORM=osx and the desired MACOS_ARCH; on Linux use PLATFORM=linux.\n"
        "The archive has no .git directory; do not run fetch-mame.sh or\n"
        "prepare-mame.sh on these already prepared sources.\n",
        encoding="utf-8",
    )
    for path in package_archive(package, Path(str(package) + ".7z")):
        print(f"{path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
