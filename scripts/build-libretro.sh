#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mame_tree="${1:-${repo_root}/build/mame}"
platform="${PLATFORM:-}"

if [[ -z "${platform}" ]]; then
    case "$(uname -s)" in
        Darwin) platform=osx ;;
        Linux)  platform=linux ;;
        MINGW*|MSYS*) platform=win ;;
        *) echo "Set PLATFORM for this operating system." >&2; exit 1 ;;
    esac
fi

jobs="${JOBS:-}"
if [[ -z "${jobs}" ]]; then
    jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
fi

build_core() {
    make -C "${mame_tree}" -f Makefile.libretro \
        platform="${platform}" \
        TARGET=mame \
        SUBTARGET=shmdp \
        SOURCES=src/mame/sega/mdconsole.cpp \
        PTR64=1 \
        -j"${jobs}" \
        "$@"
}

if [[ "${platform}" == "osx" && "${MACOS_ARCH:-$(uname -m)}" == "arm64" ]]; then
    macos_sdk="$(xcrun --sdk macosx --show-sdk-path)"
    build_core \
        CROSS_COMPILE=1 \
        LIBRETRO_APPLE_PLATFORM=arm64-apple-macos11.0 \
        LIBRETRO_APPLE_ISYSROOT="${macos_sdk}"
elif [[ "${platform}" == "win" ]]; then
    build_core MINGW64=1
else
    build_core
fi
