# Changelog

Every published version must have a dated entry written in English. The
`vVERSION` tag, `VERSION` file and entry must match before publication.
GitHub release notes are generated directly from the corresponding entry.

## [Unreleased]

## [0.1.13] - 2026-10-06

### SH2 explosion option and positioning

- Changing **SH2 Explosions** now restarts the loaded SH2 game automatically,
  applying the selected ROM mode before execution resumes. Previously the
  setting only applied after closing and reloading content, and a soft reset
  retained the old effect. The option remains disabled by default.
- Keep the new setting latched even when the SH1 donor is missing or invalid,
  preventing repeated restarts on unrelated option updates. Changing this
  SH2-only option does not restart SH1.
- Start option-triggered restarts from the beginning, even with MAME automatic
  saves enabled. Normal content loads retain their automatic-save behavior.
- Preserve SH2's native explosion movement and removal rules while importing
  SH1 artwork, palette and pose cadence. Original SH2 already brings ordinary
  airborne explosions to the ground in four game updates, about 0.13 seconds.
  The previous transplanted movement could overshoot ground height and lose
  one depth update; the visual-only adapter removes that difference.
- Extend the replacement to boss explosion particles while retaining the
  native destruction controller, object cleanup and boss-completion counters.
- Use modified-state format 2 and a new native-state subfolder. Modified states
  from 0.1.12 are rejected. Reserve the same Libretro state capacity in both
  SH2 modes so frontends can keep one buffer across option changes. Original
  states add zero padding; legacy original states remain loadable.
- Keep automatic fast-forward from accessing a missing machine if an internal
  reload fails, allowing the reload-failure message to reach the frontend.

### Validation and experimental limits

- Verify Original → SH1 → Original → SH1 changes within one frontend session,
  including threaded execution, automatic saves and a queued reset. Same-mode
  output repeats exactly; incompatible states are rejected without changing
  the running machine. Default-off SH2 and SH1 retain the 0.1.11 video and PCM
  in the measured 3,400-step and 2,400-step sequences respectively.
- Match all 34 sampled positions across two ordinary explosions to native SH2.
  Verify all eleven donor poses and all 44 image payloads in a separate
  diagnostic, and seven stage-four replacements with no cache fallback.
- Exercise a controlled boss death sequence: 21 particles use SH1 artwork,
  all follow native removal rules, and the boss-completion counter decrements
  exactly once. This is a forced death sequence, not a complete boss playthrough.
- Added guest execution has a measurable cost: that boss burst completes its
  counter update 22 video frames later. Shared animation restarts and SH2's
  particle lifetime mean the burst reaches pose eight before removal, rather
  than displaying all eleven poses. Full all-stage and all-boss coverage is
  not claimed. The original mode remains unchanged.
- The configured suite runs 108 tests: 96 pass and 12 optional native-reference
  checks are skipped. The ROM adapter also passes address and undefined-behavior
  sanitizers with the private original ROMs.

## [0.1.12] - 2026-10-06

### Optional SH1 enemy explosions in SH2

- Add the experimental **SH2 Enemy Explosions** core option. The default is
  **Original SH2**; **SH1 Artwork and Timing** applies an in-memory ROM patch
  when content loads. Closing and reloading content applies either choice.
- Read the original eleven-pose animation, all four source sizes and palette
  from the user's authenticated `jp_jp_space_harrier.smp`, placed beside SH2
  or in the frontend system directory. No ROM or game graphics are distributed,
  and neither source file is modified. Missing or invalid donors retain the
  original effect and display a message.
- Identify 50 ordinary-enemy methods from verified actor-creation sites across
  all four generic collision paths, including the stage-4 robot families.
  Preserve the original player, scenery and boss/custom callbacks. Copy SH1's shared animation handler and
  preserve its four-update pose cadence, synchronized first-pose duration,
  restart when another explosion appears, final-pose hold and palette cycle.
  Use the source drawings directly with SH2's distance projection and scaling.
- Keep the original SH2 graphics, use a separate palette and bounded shared
  graphics cache, and revert an effect to its original animation if a later
  asset allocation would overlap the cache. No fallback occurred in the tested
  stage-1 and stage-4 runs.
- Tag modified-mode Libretro save states and reject incompatible modes before
  loading their contents. Keep MAME disk/automatic states in a separate folder
  when the patch is active. Same-mode save/load reproduces video and audio.

### Content reload and validation

- Clear retained launch arguments and release the previous MAME machine when
  content closes. Reloading and switching Original → SH1 → Original now work
  with or without a deinit/init cycle, without the previous cleanup crash.
- Fix MAME automatic saves on content close by querying the current save
  manager's support status; the legacy system-flag check was always false.
- Default-off SH2 output matches 0.1.11 video and PCM over 3,400 control steps;
  SH1 matches over 2,400. Save/load reproduces 120 subsequent steps in both
  games, including an active modified explosion. Missing/invalid donor and
  cross-mode state rejection checks also pass.
- Execute all eleven imported poses in a diagnostic that holds an explosion
  in view. Match all 44 source graphics byte-for-byte against uploaded VRAM,
  and verify the shared restart and final-pose hold. Two 9,000-step scripted
  runs observe four modified effects in stage 1 and seven in stage 4, including
  the cannon robots. Lives are held at nine solely to continue these diagnostic
  runs; enemy positions and destruction logic are not forced. The first boss
  approach is visually inspected, but boss destruction is not tested.
- All 94 configured automated tests pass; 12 optional native-reference checks
  are skipped when their external observations are not configured. The new ROM
  adapter also passes address and undefined-behavior sanitizers with the private
  original ROMs.
- Known experimental-mode limitation: added guest instructions change raster
  timing in 19 introduction images (3–96 pixels per image in the measured run).
  Controlled probes isolate this to instruction cost, not palette interference.
  The enabled PCM stream also differs at sample level; audibility has not been
  assessed. The default mode has no such changes. Full all-stage playthrough
  coverage is not claimed.

### Fidelity investigation

- Added 160 synthetic native video-port reference sequences and documented
  remaining palette ordering/readback, byte-access, read-decoding and register
  differences. This audit does not change the production core.
- Confirmed 31 stale palette overwrites over 27,900 traced SH1/SH2 frame steps.
  An isolated diagnostic comparison affects only the first two rows of six
  SH2 attract images; all other images and audio in that sequence match 0.1.11.
- Identified a counter-read difference that reaches both games' random-state
  update: M2 returns a zero horizontal byte, while the port supplies changing
  horizontal bits. Wider game-state and timing consequences remain to be measured.
- Added native IRQ-expiration and direct-VRAM byte references. Documented
  retained reset state, partially uninitialized ROM padding, and the ineffective
  sound-CPU overclock option, with explicit limits on observed gameplay impact.
- Added an opt-in Libretro reload regression that reproduces the second-
  load failure in 0.1.11, including switching from SH1 to SH2. The reload defect
  is fixed above; the other audit findings remain investigation results.

## [0.1.11] - 2026-10-05

### Native DMA, copies and memory mapping

- Match M2's CPU-to-video DMA word counts, including zero and large lengths,
  and preserve source registers. Retain the native destination wrapping and
  the order of bus reads before alignment diagnostics.
- Match sequential VRAM copies, including overlapping regions, command/type
  selection and completion state. Reject unsupported DMA data writes according
  to the actual SH1/SH2 profiles.
- Restore native VSRAM wrapping and mirrors for DMA and ordinary writes. Add
  the direct write window, including byte duplication for 8-bit writes.
- Expand CPU RAM to M2's 128 KiB with distinct lower/upper halves. DMA sources
  crossing the 24-bit address boundary continue to select RAM as M2 does.
  Reset and save states include both halves.

### Impact and validation

- Added original ARM references covering 111 video-port sequences and 38 bus
  cases, with production-code tests for transfers, memory mapping and reset.
- All 96 automated tests pass with fresh native references and private ROMs.
  The DMA/bus probes also pass address and undefined-behavior sanitizers.
  The final core retains identical video and audio over 27,000 control frames;
  save/load reproduces 180 subsequent frames and audio in both games.
- In the traced SH1/SH2 sequences, all 11,163 DMA commands rewrite all three
  source registers before use. No zero/large DMA, VSRAM DMA or VRAM copy is
  observed, and RAM DMA reads use the upper bank. The previously wrong state
  therefore does not cause a visible change in these captures.
- The stage-4 and first-boss controls retain identical video and audio. Native
  VSRAM mirrors and separate RAM banks are verified independently; no visual
  improvement is claimed where none was measured.
- Older save states are incompatible with the larger RAM. Start normally from
  the original ROM. Full timing, mixed palette-write ordering, VDP read quirks
  and complete all-stage equivalence remain to be established.

## [0.1.10] - 2026-10-05

### Native video-memory fills

- Fixed full 64 KiB VRAM clears used by both SH1 and SH2. A zero fill length
  previously left stale graphics in memory; it now performs M2's complete clear.
- Matched native byte lanes, even-rounded fill counts, destination wrapping and
  completion state. Length and source registers are preserved after a fill.
- Preserve the current MDP address and command when a register is written,
  including an autoincrement change between fill setup and its data word.
  Standard Mega Drive behavior remains separate.

### Validation and further findings

- All 84 automated tests pass with fresh native references and private ROMs.
  The production fill code matches 36 original-ARM cases; runtime checks cover
  139 fills and seven complete 64 KiB clear snapshots across SH1 and SH2.
- Audio matches 0.1.9 over 27,000 frames in four control sequences. Comparing
  every frame of the two 6,000-frame attract runs finds only seven isolated
  transition-frame changes, removing stale logo or tile fragments. Every other
  frame matches. No flicker filtering was added.
- Added 98 synthetic native transfer reference sequences and an SH2 hook audit.
  The 77 restorations previously justified by SH1 or symmetry were checked
  against their own SH2 handlers; no additional incorrect opcode was found.
- Additional CPU-to-video DMA count, source-register and VSRAM/copy differences
  are documented but remain to be corrected. These measurements do not establish
  complete controller, timing or all-stage equivalence with M2.

## [0.1.9] - 2026-10-05

### SH2 pre-boss lightning

- Fixed the corrupt tile graphics during the lightning animation before bosses.
  A reconstructed instruction wrote to the source address instead of reading
  the next tile. Restored the source read performed by the original M2 block.
- Verified all 9,600 tilemap writes in the attract-mode transition before
  Trimuller: every value now matches its source tile and attributes. The
  runtime ROM remains unchanged, and audio matches 0.1.8 over 1,801 frames.
- A second stage-1 diagnostic capture validates another 9,600 tilemap writes.
  All 79 automated tests pass, including 76 synthetic executions of the
  original ARM tilemap block. Only the 48 lightning frames change in the
  compared attract-mode screenshot interval.
- SH1's repair table and the shared renderer are unchanged. Two SH1 control
  sequences and the SH2 stage-1 control sequence retain identical video and
  audio over 21,000 frames. This fix does not establish all-stage or complete
  CPU/video timing equivalence.

## [0.1.8] - 2026-10-05

### Native sprite selection

- Replaced the empirical sprite pixel budget with M2's source-column and
  sprite limits: 20 sprites / 40 columns at 320 pixels, or 16 / 32 at 256 pixels.
  Reduced, transparent and horizontally offscreen sprites consume the same
  source budget as in the original renderer.
- Read sprite attributes directly from VRAM. Matched the original table
  addressing, linked-list cycle handling, conditional X=0 termination and
  reverse drawing order, including M2's partial final-sprite behaviour.
- Matched graphics-bank and palette flags with zoom enabled or disabled, and
  preserved native attribute carries when advancing between tiles.

### Raster colour timing

- Date direct palette writes using the scanline counter passed to the renderer.
  The previous screen-position counter had a different frame origin, shifting
  colour changes to the wrong lines. A trace of 678 SH2 writes in the libretro
  core confirms the 38-line difference between these counters.
- Preserve the original ordering: render the current line, run its CPU slice,
  then show colour changes on the following line. No temporal blending added.

### Validation and limitations

- The complete production sprite method matches all 76 synthetic original-ARM
  cases, plus the earlier geometry, zoom-bank and clipping references. Address
  and undefined-behaviour sanitizer checks pass.
- Zero differences across 143,360 indexed pixels from two complete SH2 frames,
  including a sprite-heavy first-boss scene where 0.1.7 differs in 30 pixels.
- All 76 automated tests passed with fresh native references and private ROMs.
  RGB output also matches the native indices combined with the captured local
  palette for those two frames; this does not prove whole-engine timing.
- Replayed 39,020 frames across six SH1/SH2 scenarios; audio matches 0.1.7
  exactly. Save/load reproduces all 180 subsequent frames and audio in each
  game's control sequence with default settings.
- These changes also affect SH1. Remaining work includes complete CPU/IRQ
  timing, interactions between direct and ordinary palette writes, extended
  VSRAM access, other reconstructed hooks and wider game/platform coverage.

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
