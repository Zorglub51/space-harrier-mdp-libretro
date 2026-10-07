# Mark VI: unbounded SH2 sprite presentation

`mame_sh2_rendering` offers `original` (default), `mark_vi` (native refresh) and
`mark_vi_120` (experimental interpolation).
Only the authenticated SH2 cartridge enables the enhancement. The original
M2-compatible pixel path remains unchanged. No additional ROM patch, guest
RAM write, CPU overclock or extra game update is needed for Mark VI.

## Construction before quotas

The translation in `src/markv/sh2_markvi.h` follows the restored SH2 constructor
at `13B000..13D21E`. It traverses the active object chain at `FF38F2`, reads the
22-byte pose descriptors and 12-byte piece records, and retains the native
signed arithmetic, horizontal visibility tests, tile increments, palette/bank
selection, four flip combinations, mirrored double assemblies and shadow pass.
The allocation-table address is read from the live authenticated ROM operand,
so the optional SH1 explosion cache relocation remains supported.

The native emitter partitions its output into 40/80-entry buffers. Its SAT
links and transform indices are seven bits wide. Mark VI constructs a host
`std::vector` instead: each record has its own coordinates, tile attributes and
zoom value. There is no 128/256/512-entry selection array or arbitrary sprite
budget. Invalid/cyclic object chains are rejected, rather than followed forever.
The game's object pool, allocation, lifetime and deliberate invisibility flags
remain gameplay decisions. The enhancement does not create additional enemies.

Both the body and shadow passes preserve their object/piece traversal order.
Pixel sampling uses the verified M2 cell-scaling algorithm, palettes and priority
bits. Mark VI draws every intersecting entry in reverse traversal order so the
first piece wins an overlap. It does not retain previous-frame pixels.

## Timing and buffer lifetime

Read-only observers capture 128 KiB of work RAM at native constructor entry,
separately for the two producer banks. A completion observer records the native
SAT geometry for that bank. The host list is promoted only on the corresponding
complete SAT DMA upload. Link-byte repairs are ignored in the comparison;
geometry changes caused by a bank clear/replacement invalidate the snapshot.
Direct VRAM writes/fills also invalidate a displayed host list. This prevents
old title sprites from appearing with newly loaded stage artwork.

The three native RAM snapshots and their lifecycle metadata are saved. The
variable host list is rebuilt after state load. Version 0.1.17 also saves the
presentation history and pending half-frame output; earlier state layouts are
incompatible. All current rendering choices share one state size/layout.

## Optional 120 Hz presentation

The original and native-refresh Mark VI paths retain their existing cadence.
`mark_vi_120` negotiates twice the native screen refresh with libretro:
119.8454895 Hz for the supported NTSC cartridge. `retro_fps` remains the native
clock used by MAME and the audio fallback. Every two `retro_run` calls execute
one native main loop. The existing stereo PCM sequence is split between the
two calls without resampling, inserting or dropping samples. The second call
does not execute the CPU or poll game input. A pending half is completed before
a runtime cadence change; a refused frontend request preserves the prior rate.

At each native frame boundary, two emitter snapshots identify the observed
object update interval. Each matching sprite piece is drawn at two points
along that interval, including interpolated position and zoom. A two-refresh
object update therefore has four presentation steps, rather than two duplicate
pictures. Interpolation is clamped at the endpoint; there is no extrapolation.
This delays geometry by approximately one object-update interval, commonly
17–33 ms. This first implementation does not interpolate the background/ground
or generate intermediate sprite artwork. Collision and input timing remain
native, so interpolated visuals can be offset from current collision positions.

Matching uses guest object address, handler, pose/LOD descriptor, piece and
mirror/shadow identity. Tile-cache relocation uses current artwork. Changes of
size, flip or palette skip interpolation. Missing/hidden pieces disappear
immediately; new pieces appear immediately. Coordinate wraps or displacements
larger than 128 pixels in either axis snap to the current position. These are
presentation guards, not sprite/count/computing quotas. An indistinguishable
same-slot, same-handler reuse between observations cannot be proven to be the
same object; this remains an experimental visual enhancement.

Both subframes use the existing M2 pixel sampler and compositor, with the
current raster palette, tile data and priority rules. A mid-frame list rebuild
falls back to the current native list until the next frame boundary. The
software renderer substitutes the screen texture for the first half and draws
the same MAME primitives, preserving normal scaling, colour settings and UI
overlays. Pixels from consecutive frames are never blended together.

The pending second framebuffer and PCM are saved, including at odd presentation
boundaries. The framebuffer reservation matches libretro's existing maximum
4096×3072 buffer, adding roughly 50 MB to uncompressed states (about 60 MB total).
This fixed capacity avoids growing a state buffer cached by the frontend after
an option or resolution change. Transient interpolation vectors and renderer
pointers are not serialized. Same-mode state replay and runtime mode changes
are tested; changing preferences necessarily changes subsequent presentation.

No additional ROM patch, guest RAM write, CPU overclock or gameplay update is
introduced. Native Deflicker continues to control the guest lists independently.

## Evidence and limits

[SH2_MARK_VI_VALIDATION.json](SH2_MARK_VI_VALIDATION.json) records the tested core
hash and integration results. Private game data and images are not distributed.

- 5,182 native emitted records from stage 1 and 3,196 from stage 4 are found
  identically in the compiled host constructor's output.
- Controlled native-constructor runs vary all eight assembly flags and scaled/
  unscaled paths: another 7,364 records match, including mirrored assemblies.
  These modified diagnostic scenes reached 171 host entries.
- Synthetic public tests exercise 600 pieces, 200 independent object transforms,
  signed rounding, mirroring/palettes, relocated tile caches, cyclic/dead/hidden
  objects, zero-height sprites, overlap order and empty frames.
- Production-method tests check producer completion, matching uploads, relinking,
  external clears and unknown sources. Renderer/lifecycle probes pass ASan/UBSan.
- 7,000-step stage 1/3/4 runs change 1,668/1,058/1,472 video frames respectively.
  Full PCM streams and sampled 128 KiB work RAM plus eighteen 68000 registers
  match the corresponding original-rendering runs. Samples occur every 120
  video frames; this is not an instruction-by-instruction proof.
- Additional runs cover ON1/ON2, SH1 explosion artwork, state replay and threaded
  mode switching. Default SH2 and SH1 with Mark VI selected retain their measured
  baseline video/audio/game state. A title-transition capture verifies that the
  stale-logo regression was removed.

These are targeted sequences and controlled constructor comparisons, not full
playthroughs of every stage/boss or an independent original-ARM oracle for the
entire constructor. Capacity limits have been removed from this host path;
intentional blinking remains. No universal real-time performance claim is made.
The original M2 renderer still passes its 76-case native fixture.

## 0.1.17 interpolation validation

[SH2_120HZ_VALIDATION.json](SH2_120HZ_VALIDATION.json) records core hashes and
results without game assets. At equal emulated time, 14,000 presentation calls
are compared with 7,000 native-refresh calls. Full PCM streams and periodic
128 KiB RAM/eighteen-register samples match for stages 1 and 4, and stage 3 with
SH1 explosion artwork. Tests also cover both save phases, threaded mode,
repeated refresh changes, SH1 isolation, unchanged default rendering and a
frontend rejecting the new refresh rate. Synthetic tests verify four distinct
geometry steps, long lists, identity changes, cuts, holds and invalidation.
These targeted sequences do not prove full-game visual correctness.
