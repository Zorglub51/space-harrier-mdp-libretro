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
- [Changelog for every version](CHANGELOG.md)

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
- restored background colour writes and raw temporal dithering;
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
Each version has an English entry in [CHANGELOG.md](CHANGELOG.md), used as its
GitHub release notes. A matching `vX.Y.Z`
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
then verifies identical video and audio for 180 frames after a save/load cycle.
It archives the checkpoint hashes as CI artifacts. The ROM bundle is never
published as an artifact. `SH_MDP_STATE_FRAMES` can extend the replay window.

## Scope and status

An optional **SH2 Explosions** core setting imports SH1's original eleven-pose
sequence and its cadence for all exploding SH2 objects, including scenery and
player-collision effects, using
your own SH1 ROM. SH2 keeps its movement and object lifetimes. The option is
disabled by default, patches the supported SH2 ROM in memory, and automatically
restarts the game when changed.
See the [user guide](USER_GUIDE.md#optional-sh1-explosions-in-sh2) for setup and
the [timing reference](docs/SH2_EXPLOSION_TIMING.md) for the donor behavior.

Fidelity work covers SH1 and SH2 through targeted comparisons with M2. The first
portable SH1 hook translation is
checked against 31 measured executions of the original ARM block; the collision
reconstruction has also been corrected in the existing core. See
[SH1 native execution reference](docs/SH1_NATIVE_REFERENCE.md) for coverage,
reproduction steps and the remaining work. The [SH2 native reference](docs/SH2_NATIVE_REFERENCE.md)
explains its corrected line-phase reset and remaining compatibility questions.
The [raster colour reference](docs/MDP_RASTER_CRAM.md) documents direct palette
addressing and its timing limits.
The [SH2 text reference](docs/SH2_TEXT_REFERENCE.md) explains the restored direct
VRAM writes used for its font animation. The [video geometry reference](docs/MDP_VIDEO_GEOMETRY.md)
covers explicit MDP registers, restored SH2 perspective and sprite zoom. The
[native frame oracle](docs/MDP_FRAME_ORACLE.md) records zero indexed-pixel differences
on one complete SH2 stage-4 frame plus sampled SH1/SH2 lines, at identical video
state. Native shadow composition, extended sprite colours and reduced-cell
clipping replace previous approximations. The core outputs raw frames without
temporal averaging or sprite persistence.

The [sprite selection reference](docs/MDP_SPRITE_LIST.md) covers the native
sprite and source-column limits, VRAM list traversal and 76 full-renderer
synthetic cases. The [raster timing reference](docs/MDP_RASTER_TIMING.md)
explains the corrected scanline origin for palette writes.
The [SH2 lightning reference](docs/SH2_LIGHTNING_REFERENCE.md) explains the
repaired source-tile read that removes corrupt graphics before bosses.
The [transfer reference](docs/MDP_TRANSFERS.md) covers native VRAM fills,
DMA, copies, VSRAM writes and command state. The [bus reference](docs/MDP_BUS.md)
documents M2's 128 KiB RAM and DMA address decoding. The
[impact report](docs/MDP_TRANSFER_IMPACT.md) records which cases the tested game
sequences actually exercise. The [SH2 hook audit](docs/MDP_HOOK_AUDIT.md) checks restorations
previously justified by similarities with SH1 against their own SH2 handlers.

This is not yet a claim of complete pixel-perfect emulation. The
[fidelity checklist](docs/FIDELITY_STATUS.md) separates measured contracts from
remaining timing, game hooks and host presentation questions.
Android is deferred.

This is an independent preservation/research project, not an official Sega, M2,
MAME or Libretro release. The first game has received extensive testing through
Stage 1 and attract mode; later stages need broader community testing. Please
report defects with the platform, RetroArch version, exact point in the game and a
short video or screenshot when possible.

## Licence

The combined core is distributed under GPL-2.0-or-later, consistently with modern
MAME. Individual upstream files retain their own licence headers. See
[LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
