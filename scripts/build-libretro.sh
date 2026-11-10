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
elif [[ "${platform}" == "trimui-smart-pro-nextui" ]]; then
    if ! SHMDP_ZIG="$(command -v zig)" || [[ "$("${SHMDP_ZIG}" version)" != 0.16.0 ]]; then
        echo "This target requires Zig 0.16.0 on PATH." >&2
        exit 1
    fi
    export SHMDP_ZIG
    platform=linux
    trimui_tools="$(cd "${mame_tree}" && pwd)/build/trimui-toolchain"
    mkdir -p "${trimui_tools}"
    export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-${trimui_tools}/zig-global-cache}"
    export ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-${trimui_tools}/zig-local-cache}"
    # Keep GENie's host compiler native. Only the generated Linux core build
    # uses these wrappers. Do not link the handheld module against host glibc.
    for driver in cc c++; do
        printf '%s\n' '#!/bin/sh' \
            "exec \"\$SHMDP_ZIG\" ${driver} -target aarch64-linux.4.9-gnu.2.28 -mcpu=cortex_a53 -Wno-nullability-completeness \"\$@\"" \
            > "${trimui_tools}/${driver}"
    done
    printf '%s\n' '#!/bin/sh' 'exec "$SHMDP_ZIG" ar "$@"' > "${trimui_tools}/ar"
    chmod +x "${trimui_tools}/cc" "${trimui_tools}/c++" "${trimui_tools}/ar"
    # With CROSS_BUILD, MAME keeps CC native for GENie and otherwise checks
    # that host compiler for the target Clang version. Linux hosts may use GCC.
    trimui_clang_version="$("${trimui_tools}/cc" --version |
        sed -nE '1s/^.*clang version ([0-9]+\.[0-9]+(\.[0-9]+)?)([[:space:]].*)?$/\1/p')"
    if [[ -z "${trimui_clang_version}" ]]; then
        echo "Could not determine the target Clang version from Zig." >&2
        exit 1
    fi
    build_core TARGETOS=linux ARCHITECTURE=_arm64_clang PLATFORM=arm64 \
        LIBRETRO_CPU=aarch64 CROSS_BUILD=1 VERBOSE= \
        CLANG_VERSION="${trimui_clang_version}" \
        OVERRIDE_CC="${trimui_tools}/cc" OVERRIDE_CXX="${trimui_tools}/c++" \
        OVERRIDE_AR="${trimui_tools}/ar" NOASM=1 NO_OPENGL=1 DONT_USE_NETWORK=1 \
        'LDOPTS=-s -Wl,-z,defs'
    if [[ "$(uname -s)" == Darwin ]]; then
        # GENie uses the host suffix, although Zig links an ELF for this target.
        cp "${mame_tree}/shmdp_libretro.dylib" "${mame_tree}/shmdp_libretro.so"
    fi
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
