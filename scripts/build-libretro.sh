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

if [[ "${platform}" == "osx" ]]; then
    macos_sdk="${SDKROOT:-$(xcrun --sdk macosx --show-sdk-path)}"
    echo "Building macOS ${MACOS_ARCH:-$(uname -m)} with SDK ${macos_sdk}."
    case "${MACOS_ARCH:-$(uname -m)}" in
        arm64)
            build_core \
                CROSS_COMPILE=1 \
                LIBRETRO_APPLE_PLATFORM=arm64-apple-macos11.0 \
                LIBRETRO_APPLE_ISYSROOT="${macos_sdk}"
            ;;
        x86_64)
            build_core \
                CROSS_COMPILE=0 \
                LIBRETRO_APPLE_PLATFORM=x86_64-apple-macos10.15 \
                LIBRETRO_APPLE_ISYSROOT="${macos_sdk}"
            ;;
        *) echo "Unsupported MACOS_ARCH: ${MACOS_ARCH:-$(uname -m)}" >&2; exit 1 ;;
    esac
elif [[ "${platform}" == "win" ]]; then
    windows_patch="${repo_root}/patches/mame0289-libretro-windows.patch"
    if git -C "${mame_tree}" apply --check "${windows_patch}" 2>/dev/null; then
        git -C "${mame_tree}" apply "${windows_patch}"
    elif ! git -C "${mame_tree}" apply --reverse --check "${windows_patch}"; then
        echo "The Windows input source is neither clean nor already patched." >&2
        exit 1
    fi
    build_core MINGW64=1
else
    build_core
fi
