# Building the Libretro core

## Reproducible source

The scripts fetch `libretro/mame` at the exact commit recorded in `MAME_COMMIT`,
apply `patches/mame0289-space-harrier-mdp.patch`, then generate
`sh1_mdp_rom.h` from the public ROM patch table. No ROM is required to compile.

Do not substitute a newer MAME checkout without rebasing and testing the patch.

## Linux

Install a C/C++ toolchain, Git, Python 3, Make, Zip and the development packages
used by MAME's official Libretro workflow. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y build-essential git python3 zip \
  libgl1-mesa-dev libglu1-mesa-dev libegl1-mesa-dev libx11-dev libxext-dev \
  libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev libxxf86vm-dev \
  mesa-common-dev
./scripts/fetch-mame.sh
./scripts/build-libretro.sh
./scripts/package-core.sh build/mame linux-x86_64
```

## macOS

Install Xcode Command Line Tools, Git, Python 3 and Zip, then run:

```bash
./scripts/fetch-mame.sh
./scripts/build-libretro.sh
./scripts/package-core.sh build/mame "macos-$(uname -m)"
```

The script defaults to the architecture of the Mac running it. Set
`MACOS_ARCH=x86_64` or `MACOS_ARCH=arm64` explicitly for a cross-build supported
by your Xcode installation.

## Windows

When `PLATFORM=win`, `build-libretro.sh` also applies
`patches/mame0289-libretro-windows.patch` to the prepared tree. It avoids an
unused SDL dependency and accepts a tree where that patch is already applied.

The `0.1.3-sh1-textfix` test export was cross-compiled on macOS ARM64 with
MinGW-w64. Its `source-reference/` directory records the full source patch,
generated ROM header, separate Windows patch, exact build command and binary
verification. That command uses the native host compiler for build tools and
explicit MinGW overrides for target objects. Do not substitute the Linux
environment settings below when reproducing that macOS-hosted build.

The release workflow cross-compiles the Windows x86_64 core from Ubuntu with the
POSIX MinGW-w64 compiler, matching upstream libretro/MAME CI:

```bash
sudo apt-get install -y mingw-w64 gcc-mingw-w64-x86-64-posix \
  g++-mingw-w64-x86-64-posix
export CC=x86_64-w64-mingw32-gcc-posix
export CXX=x86_64-w64-mingw32-g++-posix
export AR=x86_64-w64-mingw32-ar
PLATFORM=win ./scripts/build-libretro.sh
./scripts/package-core.sh build/mame windows-x86_64
```

## Outputs

The core is built as the small `shmdp` subtarget using only
`src/mame/sega/mdconsole.cpp` and its dependencies. `package-core.sh` finds the
resulting shared library and creates a release-ready archive under `out/`.

GitHub Actions runs the same scripts. `build.yml` produces downloadable workflow
artifacts; `release.yml` publishes them when a `v*` tag is pushed.

## Standalone ROM patcher

The core patches the supported original in memory, so end users do not need this.
For testing another emulator:

```bash
python3 rompatch/patch.py jp_jp_space_harrier.smp
```

This creates `jp_jp_space_harrier_patched.smp` and leaves the source untouched.
