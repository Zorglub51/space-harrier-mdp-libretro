# Changelog

Every published version must have a dated entry written in English. The
`vVERSION` tag, `VERSION` file and entry must match before publication.
GitHub release notes are generated directly from the corresponding entry.

## [0.1.7] - 2026-10-05

### Rendering matched to M2 measurements

- Corrected shadows: sprite operators now follow the composition rules of the
  original ARM code. Harrier's shadow no longer becomes a highlighted area.
- Matched colour conversion to the M2 engine's RGB output: each channel is
  34 times its CRAM value at normal intensity, or 17 times in shadow.
  Added support for the second palette bank for sprites and the backdrop.
- Corrected clipping of reduced sprite cells at the left edge, following the
  behaviour measured in M2.
- Removed the old two-frame background averaging and optional sprite
  persistence. The core outputs each raw frame, preserving alternating pixels
  and colours.

### Save states

- Save states now include all MDP graphics memory and the audio filter history.
  After loading a state, SH1 and SH2 reproduce all 180 subsequent frames and
  their audio exactly in the control sequences, using default settings.
- States from earlier versions are incompatible; restart from the original ROM.

### Validation and limitations

- Zero differences across 82,240 indexed pixels at identical video state: one
  complete SH2 stage-4 frame (320 × 224), plus 11 lines per scene from SH2 stages
  1 and 3 and one SH1 scene. The reference was obtained by executing the original
  ARM engine, with its colour conversion checked separately.
- Public oracles without ROM data: 208 composition cases and 4,115 colour
  conversion cases, with tests of the actual distributed C++ and save/load replay.
- All 71 automated tests passed. Local validation included fresh ARM references
  and privately supplied original ROMs.
- Replayed 39,020 frames across six SH1/SH2 scenarios; audio matches the 0.1.5
  reference on those sequences. Video changes reflect the corrections above.
- These measurements do not yet establish equivalent timing, sprite limits,
  all game hooks or all stages. The M2 application's GPU presentation filters
  remain outside this validation scope.

## [0.1.6] - 2026-10-05

### SH2 perspective and sprites

- Removed the 53-line offset and artificial stretching of SH2 scenery: planes
  now use the transformation for the displayed scanline, as M2 does. This
  restores their position relative to sprites, particularly in stages 1 and 4,
  where objects appeared too low.
- Added support for all 64 direct MDP registers. Plane and sprite-zoom registers
  explicitly select and enable their tables. Stale table contents can no longer
  activate a disabled effect.
- Render both planes using M2 coordinates, dimensions, flips, palettes and
  priorities, with wrapping or edge clamping. Removed SH2 rules that hid certain
  mountain and ceiling lines.
- Matched vertical sprite zoom to M2 calculations: enlargement is allowed,
  zero-height sprites are invisible, and vertical distance wraps over 10 bits.

### Validation and limitations

- Compared the distributed C++ with original ARM execution results: 68 register
  addressing cases, 30 plane cases, and sprite geometry, table-selection and
  reduction cases. Public fixtures contain no ROM data.
- Compared SH2 captures from stages 1, 3 and 4, attract mode and ranking, as well
  as both 6,000-frame SH1 sequences. Audio is unchanged on the compared sequences.
  Zoom corrections can also affect some SH1 sprites; SH1 video is not claimed
  to be identical to the previous version.
- No flicker filter or persistence was added. M2 timing, extended sprite
  palettes, some screen-edge cases and validation of all stages still need
  further investigation.
- Older save states are incompatible with the extended registers; start from
  the original ROM.

## [0.1.5] - 2026-10-05

### SH2 fix

- Restored the direct access window to lower video memory. Writes that rebuild
  the ranking font now reach their destination and update the character cache.
- Removed palette-based font remapping. The "RANKING LIST" title and initials
  use the tiles written by the game, including their appearance animation.
  No font is substituted in the ROM.

### Validation and limitations

- Verified the cause in M2 code, bus traces and video memory: the 3,040 bytes
  written for the font had previously been discarded.
- Compared SH2 title, gameplay, first-boss, ranking and Yees Land sequences.
  Audio is unchanged on the compared sequences.
- SH1 preserves the complete video and audio streams of both 6,000-frame
  reference sequences. No additional flicker filter was introduced.
- Scenery persisting behind the ranking screen, geometry in some stages and
  M2 timing remain to be addressed. This version does not claim validation of
  all stages or interactive Windows/Linux sessions.

## [0.1.4] - 2026-10-05

### SH2 fixes

- Restored `MOVE.L D4,D1` in the scenery line generator: the previous `NOP`
  omitted the phase reset to -32. The correction is established by executing
  M2's original ARM block on 33 cases.
- Decoded direct colour writes at `C00400..C004FF`: each address selects its
  palette entry, including `C00462` for SH2. Multiple colours written for the
  same scanline are retained separately.
- Added reset and save-state handling for pending palette writes.
- Added an SH2 Windows launcher and details of both ROMs to the guides.
  SH1 and SH2 continue to share the same core.

### Validation and limitations

- Original ARM execution references and public tests without ROM data cover
  the line counter and colour addressing. Compared 39,000 SH2 frames across
  five scenarios on Mac, reaching the first boss.
- SH1 preserves the complete video and audio streams exactly on two 6,000-frame
  sequences: attract mode and scripted input. The palette fix does not change
  SH2 audio.
- No additional flicker filter or sprite persistence was introduced.
- SH2 ranking characters and background remain incorrect; some scenery geometry
  still needs comparison with M2.
- Complete rendering and timing equivalence with M2, full playthroughs and
  interactive Windows/Linux sessions remain to be validated.
- Older save states are incompatible with this revision; start the game
  normally from the original ROM.

## [0.1.3] - 2026-10-05

### Fixes

- SH1 stage and boss announcements display the correct characters again.
  SH2-specific font compatibility is now restricted to its recognised original
  ROM.
- SH1: corrected the collision instruction that overwrote the iteration counter
  in stage 1.
- SH2: added original-ROM recognition in the core, instruction reconstruction,
  corrected input reads and extended colour memory handling.
- Preserved the flicker observed during testing; no additional flicker filter
  is enabled.

### Downloads

- Complete archives for Windows x86_64, Linux x86_64, macOS Intel and macOS
  Apple Silicon, with guides, core information and SHA-256 checksums.
- SH1 test launcher for Windows and installer for macOS.
- Complete corresponding source, including the pinned MAME revision, patches
  and build tools. No ROM is included.
- Release notes are published from this changelog. Subsequent versions use the
  same mechanism when a `vX.Y.Z` tag is created.

### Validation and limitations

- Compared the first portable SH1 block against 31 measured executions of M2's
  original ARM code. This block remains tested separately; the distributed core
  still uses reconstructed 68000 instructions.
- Visually checked SH1 text on Mac. Across the compared 6,000-frame sequences,
  SH2 retains exactly the same video and audio; SH1 audio is also unchanged.
- Automated tests cover ROM profiles, reconstruction, release tools and archives.
  All four architectures are built before publication.
- Interactive Windows/Linux sessions and full playthroughs remain to be
  validated. Save states and overall fidelity to M2 are still under development.

### Usage

Download the archive for your operating system and extract it with 7-Zip or a
compatible tool. On Windows, run `TESTER_SH1_WINDOWS.cmd` to select RetroArch x64
and your original SH1 ROM. On Mac, use `INSTALLER_MACOS.command`. On Linux,
install the `.so` and `.info` files as described in the included guide.

The `source` archive is intended for rebuilding; it is not needed to play.
Use the `SHA256SUMS` files to verify downloads.

## [0.1.2] - 2026-10-05

Local test version, not published on GitHub: SH1 collision fix, first measured
ARM reference, and Windows x64 export with a test launcher.

## [0.1.1] - 2026-08-08

- Released cores for Windows x86_64, Linux x86_64, macOS Intel and Apple Silicon.
- Added a macOS installer and instructions for installing core information.
- Provided the corresponding source archive.

[Full 0.1.1 changelog](https://github.com/Zorglub51/space-harrier-mdp-libretro/compare/v0.1.0...v0.1.1).
