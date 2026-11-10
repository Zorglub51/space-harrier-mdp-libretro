#!/usr/bin/env python3
"""Check that the NextUI download is a loadable Linux/AArch64 libretro module."""

import argparse
import os
from pathlib import Path
import re
import struct
import subprocess


SYSTEM_LIBRARIES = {
    "ld-linux-aarch64.so.1", "libc.so.6", "libm.so.6", "libdl.so.2",
    "libpthread.so.0", "librt.so.1", "libutil.so.1",
}
LIBRETRO_API = {"retro_" + name for name in """
    init deinit api_version get_system_info get_system_av_info set_environment
    set_video_refresh set_audio_sample set_audio_sample_batch set_input_poll
    set_input_state set_controller_port_device reset run serialize_size serialize
    unserialize cheat_reset cheat_set load_game load_game_special unload_game
    get_region get_memory_data get_memory_size
""".split()}


def verify(core: Path, readelf: str):
    with core.open("rb") as binary:
        header = binary.read(64)
    if (len(header) != 64 or header[:7] != b"\x7fELF\x02\x01\x01" or
            struct.unpack_from("<HH", header, 16) != (3, 183)):
        raise ValueError("expected a little-endian AArch64 ELF64 shared object")

    def inspect(*flags):
        return subprocess.check_output([readelf, "--wide", *flags, str(core.resolve())],
                                       text=True, env={**os.environ, "LC_ALL": "C"})

    dynamic = inspect("--dynamic")
    if (re.search(r"\b(?:RPATH|RUNPATH|TEXTREL|RELR|RELRSZ|RELRENT)\b", dynamic) or
            re.search(r"^\s*INTERP\s", inspect("--program-headers"), re.M)):
        raise ValueError("unexpected search path, interpreter or unsupported relocations")
    dependencies = set(re.findall(r"\(NEEDED\)\s+.*?\[([^\]]+)\]", dynamic))
    if "libc.so.6" not in dependencies or not dependencies <= SYSTEM_LIBRARIES:
        raise ValueError(f"unexpected shared dependencies: {sorted(dependencies)}")

    versions = inspect("--version-info").partition("Version needs section")[2]
    glibc = []
    for name in re.findall(r"\bName:\s+(\S+)", versions):
        version = re.fullmatch(r"GLIBC_(\d+)\.(\d+)(?:\.(\d+))?", name)
        if not version:
            raise ValueError(f"unsupported runtime version requirement: {name}")
        glibc.append(tuple(int(part or 0) for part in version.groups()))
    if not glibc or max(glibc) > (2, 28, 0):
        raise ValueError(f"expected glibc requirements at or below 2.28: {sorted(set(glibc))}")

    exports = set()
    imports = set()
    for line in inspect("--dyn-syms").splitlines():
        columns = line.split()
        if len(columns) >= 8 and columns[3:6] == ["FUNC", "GLOBAL", "DEFAULT"]:
            if columns[6].isdigit():
                exports.add(columns[7].partition("@")[0])
            elif columns[6] == "UND":
                imports.add(columns[7])
    if missing := LIBRETRO_API - exports:
        raise ValueError(f"missing libretro functions: {', '.join(sorted(missing))}")
    if "memset@GLIBC_2.17" not in imports or "memset" in exports:
        raise ValueError("expected the system AArch64 memset with no exported shim")

    version = ".".join(map(str, max(glibc))).removesuffix(".0")
    print(f"AArch64 ELF64, highest glibc requirement {version}, "
          f"{len(LIBRETRO_API)} libretro functions, dependencies: {', '.join(sorted(dependencies))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--readelf", default="readelf", help="GNU readelf (greadelf on macOS)")
    args = parser.parse_args()
    try:
        verify(args.core, args.readelf)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"TrimUI ABI check failed: {error}\n")


if __name__ == "__main__":
    main()
