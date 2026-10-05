# Space Harrier MDP — Libretro core

This project makes the Mega Drive Mini 2 editions of **Space Harrier** and
**Space Harrier II** playable in
RetroArch on desktop operating systems. It combines a narrowly scoped MAME 0.289
Libretro build with the missing MDP video behaviour and repairs the original game
code in memory at launch.

The repository and release archives contain **no game ROM**. You must provide your
own original files extracted from hardware you own.

## Download and play

Choose the archive for your operating system on the
[Releases](../../releases) page, then follow:

- [Guide utilisateur en français](GUIDE_UTILISATEUR.md)
- [English user guide](USER_GUIDE.md)
- [Changelog de chaque version](CHANGELOG.md)

Releases provide complete `.7z` downloads for Windows x86_64, Linux x86_64,
macOS Intel and macOS Apple Silicon. Extract the archive matching your machine
with 7-Zip or a compatible tool. The `source` archive is only needed to rebuild.
Each download has SHA-256 checksums and a build manifest recording its revision.

The supported originals are:

```text
Space Harrier     jp_jp_space_harrier.smp     4,063,232 bytes  e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72
Space Harrier II  jp_jp_Space_Harrier_II.smp  3,670,016 bytes  80f576af01d6413c0b92073e2f947b0431f12a74
```

The core recognises these exact files and applies the reconstruction in RAM. Your
file on disk is not modified. A standalone patcher is also included in
[`rompatch/patch.py`](rompatch/patch.py) for emulator developers and archival use.

## What is implemented

- reconstruction of the 68000 instructions replaced by M2 native hooks;
- direct MDP graphics RAM and sprite source;
- 128-entry MDP colour RAM without destructive wraparound into sprite palettes;
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
Each version has an entry in [CHANGELOG.md](CHANGELOG.md). A matching `vX.Y.Z`
tag runs the public tests and builds all four cores plus their corresponding
source archive. The release becomes public only after all downloads pass the
revision and integrity checks. See [Publishing](docs/BUILDING.md#publishing-a-revision)
for the revision procedure.

## Non-regression tests

`python3 -m unittest discover -s tests -v` checks both reconstruction tables on
every push and pull request without requiring copyrighted data. If
`SH_MDP_ROM_DIR` points to a private directory containing the two pristine files,
the same command additionally verifies every original opcode and both complete
patched-ROM hashes.

GitHub Actions also contains an optional private gameplay job. Configure the
repository variable `SH_MDP_ROM_BUNDLE_URL` with a URL to a private ZIP containing
the two files above. If that endpoint needs a bearer token, store it as the
`SH_MDP_ROM_BUNDLE_TOKEN` repository secret. The job builds the Linux core, runs
6,000 deterministic frames for each ROM, validates video production and geometry,
and archives the checkpoint hashes as CI artifacts. The ROM bundle is never
published as an artifact.

## Scope and status

Fidelity work now starts with SH1. The first portable M2 hook translation is
checked against 31 measured executions of the original ARM block; the collision
reconstruction has also been corrected in the existing core. See
[SH1 native execution reference](docs/SH1_NATIVE_REFERENCE.md) for coverage,
reproduction steps and the remaining work. Android is deferred.

This is an independent preservation/research project, not an official Sega, M2,
MAME or Libretro release. The first game has received extensive testing through
Stage 1 and attract mode; later stages need broader community testing. Please
report defects with the platform, RetroArch version, exact point in the game and a
short video or screenshot when possible.

## Licence

The combined core is distributed under GPL-2.0-or-later, consistently with modern
MAME. Individual upstream files retain their own licence headers. See
[LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
