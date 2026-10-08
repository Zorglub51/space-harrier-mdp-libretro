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
The game's object pool, allocation, lifetime and gameplay invisibility flags
remain gameplay decisions. Version 0.1.21 additionally lifts the stage 7 boss's
verified near-camera visibility budget, described below. The enhancement does
not create additional enemies.

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
The constructor also writes an overflow partition at `FF118A`/`FF140C` with
counts at `FF140A`/`FF168C`. The interrupt routines at `0ADF10`/`0AE02C` upload
it into the tail of the 80-entry SAT on a later refresh. Version 0.1.18 records
this partition's masked geometry/count at constructor completion, then copies
that signature alongside the displayed snapshot on the full SAT upload.

An overflow upload preserves an already active host list only when its source,
length, destination, stride, masked geometry and the untouched SAT prefix are
validated. The producer may already be rebuilding, so the displayed signature
remains valid independently of its current ready flag. With CPU overclocking,
the same bank may even have completed its next generation before the partial
upload occurs. Version 0.1.20 also accepts that completed bank's exact overflow
signature/count, provided the untouched VRAM prefix still matches the displayed
head. It retains the displayed complete geometry until the next full head
upload; it does not promote the next generation on an overflow DMA. The host
list already includes both partitions before quotas; no second list is added.
Unknown writes/fills, mismatches and external clears still invalidate the list.
This prevents old title sprites from appearing with newly loaded stage artwork.
No framebuffer persistence or game-side overclock is used.

The three native RAM snapshots and their lifecycle metadata are saved. The
variable host list is rebuilt after state load. Version 0.1.17 also saves the
presentation history and pending half-frame output; earlier state layouts are
incompatible. Version 0.1.18 adds the displayed primary/overflow signatures and
also requires new states. All current rendering choices share one state
size/layout.

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

Matching uses guest object address, handler (object offset `0x10`), pose/LOD descriptor, piece and
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

## Overflow-upload regression (0.1.18)

[SH2_MARK_VI_V018_VALIDATION.json](SH2_MARK_VI_V018_VALIDATION.json) records the
corrected core and checks. Stage 5 column rows were missing in both native and
120 Hz Mark VI because the overflow DMA disabled the host renderer. Captures
of the same deterministic sequence confirm removal of that defect. A separate
controlled boss burst using SH1 artwork had 39 invalidations in 341 native
refresh observations before the fix and none afterwards. The same corrected
burst passed at 120 Hz and with native Deflicker ON1. It uses a synthetic boss
controller and controlled particle coordinates, not a natural boss-1 defeat;
other intentional or unidentified blinking is not certified absent.

## Overclocked producer regression (0.1.20)

[SH2_MARK_VI_V020_VALIDATION.json](SH2_MARK_VI_V020_VALIDATION.json) records the
additional bug reported after 0.1.18. At 400% CPU speed, 129 rejected overflow
uploads in a stage 5 collision run all matched the latest completed tail of the
same bank. The displayed prefix remained intact, and the transfers occurred
during vertical blanking. The three columns remained visible in game object
data; their SH1 explosion cache was inactive. Thus neither deliberate blinking,
tile-cache exhaustion nor transfers during visible scanlines explained the gaps.

The extended authentication removes the invalidations without advancing the
displayed snapshot early. Six before/after runs cover 100/200/400% CPU clocks,
native and 120 Hz rendering, 4:3 and widescreen, SH1 and original explosions,
Deflicker OFF/game/ON1/ON2, and threaded execution. All preserve full PCM and
sampled RAM/CPU state. Original rendering, the default-clock collision sequence
and the tested ON2 sequence retain their video hashes. The 400% widescreen
120 Hz collision window has 68 invalid refreshes before the fix and zero after.

A separate first-boss run uses normal aiming/firing inputs and keeps player lives
at nine to reach the scene. Boss HP, RNG and object data are not changed by the
diagnostic. At 400%, widescreen, 120 Hz and SH1 artwork, the native destruction
controller runs on frames 8931–9015 in both builds. Its 21 explosion activations,
particle traces, sampled RAM and 8,011,106 stereo audio frames match. Invalid
refreshes in the 8931–9100 destruction window fall from 49 to zero.

Two 0.1.19 save states taken at odd/even presentation phases load in 0.1.20 and
replay 240 frames deterministically; their audio matches the older core.
The saved-state layout is unchanged. These are specific regression checks,
not certification that every animation in both games is free of defects.

## Stage 7 boss's upstream visibility budget (0.1.21)

The native body handler at `16D6EA` masks alternating nearby segments at
`16D756..16D774`, based on the leader's counter, the segment index and the
distance threshold at `FF38CA >> 2`. It sets bit 7 of object byte `+2B` before
the sprite constructor runs. Mark VI previously honored that flag even though
it was another display budget. This defect is separate from the overflow-DMA
validation fixed in 0.1.20: the extended renderer stays active throughout it.

The same flag also hides coincident trailing segments through `16D820..16D836`.
Re-evaluating that condition from final object coordinates is insufficient:
another object can update the leader later in the same game step. Read-only
instruction observers therefore track the actual executed branch. They are
installed only for the authenticated SH2 cartridge with matching instructions;
debug reads and unrelated PCs cannot change the classification.

At constructor entry, only the private snapshot's visibility bit is cleared
for a traced budget mask on a matching live boss-body handler/descriptor. Guest
RAM, the native SAT, ROM contents and CPU execution remain unchanged. Coincident
segments and other actors keep their masks. Both native-refresh and 120 Hz Mark
VI consume these snapshots; Original (M2) retains the native image and cadence.

A saved provenance table covers every aligned object address in the existing
64 KiB object address domain; it is not a sprite quota. Reset clears it, while
save/load restores it alongside the normalized snapshots and interpolation
history. **Earlier save states are incompatible with 0.1.21.**

[SH2_MARK_VI_V021_VALIDATION.json](SH2_MARK_VI_V021_VALIDATION.json) records the
regression results without private ROM data, RAM dumps or screenshots.
