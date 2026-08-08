# Space Harrier MDP — Libretro core

This project makes the Mega Drive Mini 2 edition of **Space Harrier** playable in
RetroArch on desktop operating systems. It combines a narrowly scoped MAME 0.289
Libretro build with the missing MDP video behaviour and repairs the original game
code in memory at launch.

The repository and release archives contain **no game ROM**. You must provide your
own original `jp_jp_space_harrier.smp` file extracted from hardware you own.

## Download and play

Choose the archive for your operating system on the
[Releases](../../releases) page, then follow:

- [Guide utilisateur en français](GUIDE_UTILISATEUR.md)
- [English user guide](USER_GUIDE.md)

The expected original file is 4,063,232 bytes with SHA-1:

```text
e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72
```

The core recognises this exact file and applies the reconstruction in RAM. Your
file on disk is not modified. A standalone patcher is also included in
[`rompatch/patch.py`](rompatch/patch.py) for emulator developers and archival use.

## What is implemented

- reconstruction of the 68000 instructions replaced by M2 native hooks;
- direct MDP graphics RAM and sprite source;
- per-line scaling used by the scenery and large sprites;
- restored background colour writes and stable temporal dithering;
- relaxed sprite output that retains deliberately alternating entries;
- compatibility guards found during long play sessions: divide-by-zero, missing
  Stage 1 trees, exhausted shot counter and Stage 1 boss completion;
- direct loading of `.smp`, `.bin`, `.md` and `.gen` files in RetroArch.

## Build it yourself

The build is pinned to libretro/MAME commit
`85eaed9c22242206b68eaca8310cf0dbde331b43` (MAME 0.289).

```bash
./scripts/fetch-mame.sh
./scripts/build-libretro.sh
./scripts/package-core.sh build/mame linux-x86_64
```

See [Building](docs/BUILDING.md) for dependencies and platform details. GitHub
Actions builds Linux x86_64, Windows x86_64, macOS Intel and macOS Apple Silicon.
Tags of the form `v*` create a public release containing all four archives.
Each release also includes a complete corresponding-source archive with the
pinned MAME tree already patched.

## Scope and status

This is an independent preservation/research project, not an official Sega, M2,
MAME or Libretro release. The first game has received extensive testing through
Stage 1 and attract mode; later stages need broader community testing. Please
report defects with the platform, RetroArch version, exact point in the game and a
short video or screenshot when possible.

## Licence

The combined core is distributed under GPL-2.0-or-later, consistently with modern
MAME. Individual upstream files retain their own licence headers. See
[LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
