# SH1 enemy-explosion timing reference for the optional SH2 modification

This reference describes the original SH1 destruction handler used as the donor
for the optional SH2 enemy-explosion modification. It is not evidence that every
SH1 enemy, boss or player effect uses this sequence. The forced-object checks
below are distinct from ordinary-play integration tests. The observed sequence
uses guest handler `0x1D7404` and eleven poses, with descriptor bases `0x0D84`
through `0x10F4` at a stride of `0x58` bytes.

## Clock and shared animation state

The SH1 main update increments the longword at `0xFF3D08` and the word at
`0xFF1C3E` at guest `0x142DB4` and `0x142DBA`. These are game-update counters,
not a count of every displayed video frame. A normal update takes two video
frames in the observed run; pauses and updates crossing a video-frame boundary
must not be treated as additional animation ticks.

The destruction handler uses three shared words:

| Address | Meaning |
| --- | --- |
| `0xFF1C38` | Next pose to load; zero requests initialization |
| `0xFF1C3C` | Last observed value of `clock >> 2` |
| `0xFF1C3E` | Game-update clock |

When the phase is zero, the handler records `clock >> 2`, loads pose 1 and sets
the phase to one. Otherwise it compares that quotient with the saved value. If
it changed, the handler records the new quotient and loads one next pose when
the phase is in the range 1–10. It does not catch up by loading several poses
when the clock jumps. Phase 11 keeps the last image.

Consequently, later poses normally last four game updates, or eight video
frames. The first pose lasts until the next multiple-of-four clock boundary;
it is not an independent fixed-duration eight-frame timer. The word clock also
wraps naturally, and the comparison uses the quotient of the wrapped word.

Observed creation paths clear the shared phase without resetting the clock or
saved quotient. A new destruction therefore restarts the animation shared with
other active explosions. In the normal run, an older object's descriptor could
remain on pose 4 while a new object restarted the shared graphics at pose 1.

## Graphics and distance selection

Each pose contains four 22-byte records. Their tile counts are 4, 30, 80 and
154, with image dimensions 16×16, 48×40, 80×64 and 112×88 pixels. All eleven
poses have matching piece geometry for a given distance level.

The loader beginning at `0x1D74A8` streams all four sizes into a shared upper
VRAM area. Its starting tile is read from `0xFF1C0A`; the byte destination is
`0xD10000 + (tile << 5)`. For each record it copies `tile_count * 32` bytes and
sets the record's logical slot in the table at `0xFF3D16` to
`(tile & 0x7FF) | 0x800`. It then advances the tile by that record's count.
All poses reuse the same 268 tiles, or 8,576 bytes. Keeping all eleven poses
resident would require 94,336 bytes and would not reproduce this shared-cache
behavior.

The common object pass at `0x172558` selects the size after running the object's
handler. For a positive signed depth `z`, with the ordinary flags used by this
effect:

```text
s = ROM.word(0x3C7104 + 2 * (z >> 6))
lod = min(3, (4 * s) >> 11)
width = descriptor[lod].width_in_tiles
zoom = (s * ROM.word(0x3C6904 + 2 * (width + 0x019F))) >> 12
```

The initial object is created with distance level zero; the next common update
computes its level and zoom. For positive depths up to `0x1200`, the donor
tables select level 3 at 1–2111, level 2 at 2112–3263, and level 1 at 3264–4608.
These thresholds do not replace the original lookup tables for other depths or
object flag variants. The normal trace checked 205 writes by the actual size
selector against this formula, with no mismatch.

The animation has no fixed expiration timer. The handler continues its usual
motion and projection and unlinks the object when depth or horizontal clipping
requires it. Reaching pose 11 alone does not delete it. An SH2 transplant must
distinguish this donor animation rule from the host game's enemy-object motion
and removal rules.

## Palette

The source palette bank used by the observed effect is bank 3. Its base palette
is available in the SH1 ROM at `0x393AEA`; the modification can obtain it from
the user's donor ROM rather than embedding game data. Across the 44 extracted
images, the used pixel indices are 0, 5, 6, 7, 8, 10, 11 and 12; index zero is
transparent.

Only index 8 among those used indices changes in the observed normal palette
cycle. Guest `0x0F4B46` schedules its update when
`(RAM.long(0xFF3D08) & 7) == 2`. The cycle state is a separate longword at
`0xFF1C1A`, independent of explosion creation:

```text
if state > 5:
    state = 0
    red_level = 7
else if state <= 2:
    red_level = 7 - state
else:
    red_level = state + 2
write red-only CRAM color with that 3-bit level
state += 1
```

For incoming states 1–6, the red levels are 6, 5, 5, 6, 7, 7. Each step lasts
eight game updates, normally sixteen video frames. All 45 observed writes in
the trace followed this sequence. The native normal RGB conversion is 34 times
each 3-bit component; shadow uses 17 times the component. Holding one captured
palette across every pose would omit this independent color animation.

Using a separate extended palette bank for the SH2 modification avoids changing
the host's existing colors. A scan of SH2's 384 original descriptor records
(`0x458`–`0x2558`, end exclusive) found 1,534 pieces, all without the extended
palette bit that the adapter adds. This establishes separation for those
assets, not for every possible custom SAT-writing path. Integration still has
to preserve the donor cycle's clock and phase behavior.

The adapter anchors the cycle to SH2's corresponding game-update
clock. This reproduces the formula and cadence, not an absolute presentation
phase shared between two independently running games. For ordinary enemy
deaths, it also retains SH2's immediate constructor-time size selection and
its projection tables. Those are
host-geometry choices; SH1's initial level-zero sample is not claimed to be
reproduced. At ordinary-enemy construction, when there is no other active
modified explosion, the adapter preloads pose one so the new object has valid
graphics. When another modified
explosion is active, it retains the current shared pixels until the next
handler update, preserving the donor's shared restart sequence. Both paths
leave the shared phase at zero so that the first actual handler update
establishes its quotient at the donor's timing boundary. The initial preload
without an existing active effect is another explicit host adaptation, not a
claim that the first displayed image has the same cache history as SH1.

## Executed evidence and limits

The read-only baseline used the unmodified SH1 donor ROM, the frozen v0.1.11
core with SHA-256
`2d599feb150c90b263db19f0e94ac918805c069b70302aee281ec1a84a106f2b`,
and 2,500 scripted frontend steps. Lua taps recorded counter writes, object
descriptors, size selections and palette writes. The normal run reached the
first six poses before the selected enemy explosion moved out of its lifetime.

A separate diagnostic kept the same robot destruction object (`0xFF2254`) in
view by writing only its position, depth and vertical velocity after each
sample. It did not change the guest handler, graphics, descriptor, animation
counters, ROM or core. This forced-object run executed all eleven poses:

| Pose | Sampled video frame | Game clock |
| --- | --- | --- |
| 1 | 2406 | 505 |
| 2 | 2412 | 508 |
| 3 | 2420 | 512 |
| 4 | 2428 | 516 |
| 5 | 2436 | 520 |
| 6 | 2444 | 524 |
| 7 | 2452 | 528 |
| 8 | 2460 | 532 |
| 9 | 2468 | 536 |
| 10 | 2476 | 540 |
| 11 | 2484 | 544 |

The object still held pose 11 at sample 2598, clock 563. This confirms the
handler's final-pose hold, not an ordinary enemy's natural survival time. Frame
samples can fall between instructions of a game update; the clock and tapped
writes are the timing contract. The donor handler and lookup tables were also
read directly from the local ROM, with the port's audited opcode repairs
applied only to an analysis buffer for disassembly.

Private reproduction material is kept under
`/tmp/sh-explosion-mod-20261006/sh1`: `capture.py` and `dump.lua` generate the
normal trace, and `synthetic/capture.py` with `synthetic/dump.lua` generates the
forced-object trace. Both use the repository's libretro regression frontend.
Run the first script with `SH1 scripted --frames 2500`, and the second with
`SH1 scripted --frames 2600`. These local scripts require the private ROM and
frozen core at their recorded paths; no game pixels, palette bytes, ROM dumps
or screenshots are included in this public reference.

## Executed SH2 transplant check

A separate 3,400-step diagnostic ran the enabled modification in the v3
candidate core, SHA-256
`f107478240a0b1213c54469bcd8455816666f289b492ba8f7769e13784284595`.
It kept two naturally created enemy explosions in view using only writes to
their position, depth and vertical velocity. Their handlers, descriptors,
animation counters and game clock were not modified by the diagnostic.

After the second creation, the actual relocated handler loaded poses 1–11 at
game clocks `891, 892, 896, 900, 904, 908, 912, 916, 920, 924, 928`.
The corresponding sampled frames were `3092, 3094, 3102, 3110, 3118, 3126,
3134, 3142, 3150, 3158, 3166`. Pose 11 was still active at sample 3398,
clock 1044, with zero fallbacks. This exercises the short initial duration at a
quotient boundary and the final-pose hold through the actual transplanted code.

The second creation occurred at frame 3090, clock 890, while the first effect
was displaying pose 5. Both the cache bytes and its write count stayed unchanged
through that constructor. The next handler update restarted the shared cache at
pose 1, clock 891. Thus the active-cache creation path did not advance the
visible restart early.

Caches were sampled at the actual phase writes, after the guest graphics copy
had completed. Every one of the 44 donor image payloads matched its destination
bytes exactly across the full eleven-pose sequence; all 17 observed uploads
matched their expected 8,576-byte pose payload. This is a graphics-transfer and
animation-state check, not a claim that all rendered screen pixels or all SH2
gameplay paths have been validated.

The private harness and result are under
`/tmp/sh-explosion-mod-20261006/sh1/forced-sh2`, with `analyze.py` validating
`forced-sh2-reference/RESULT.json` against the donor ROM and saved cache data.
Its `capture.py` accepts `SH2 reference --frames 3400 --label forced- --core
<candidate-core>` and explicitly selects the optional SH1 explosion style.

## Airborne-position audit of v0.1.12

An ordinary explosion does not keep its impact altitude indefinitely in either
original game. Both constructors retain the object's signed vertical position
at offset `+0x02` and set vertical velocity at `+0x06` to
`-(y arithmetic-shift-right 2)`: SH1 at `0x170068`–`0x170070`, and SH2 at
`0x139BB4`–`0x139BBC`. The original SH2 handler adds this velocity and clamps a
positive result to zero at `0x137FA8`–`0x137FBA`. It normally reaches ground
level after four game updates. World X is at `+0x00`, depth at `+0x0A`, and the
projected screen coordinates at `+0x0C` and `+0x0E`.

Two 3,180-step traces compared original and enabled modes in the same v0.1.12
candidate, SHA-256
`851917729d919bd91a739c85fe0b0d586daf4e74e345fc2ca9306adab745ea9c`.
They observed naturally triggered enemy destructions with read-only taps; no
position or animation field was forced. For the first explosion, both modes
started at world Y `-10318`, velocity `2580`, projected Y `28`. Their next three
updates had identical world Y `-7738`, `-5158`, `-2578` and projected Y
`54`, `73`, `95`. Both reached projected Y `121` at frame 3065. The modification
therefore did not place this effect on the ground immediately: the rapid
descent was already present in original SH2.

The transplanted SH1 movement nevertheless differed in a concrete way. SH1
tests the old height before adding velocity (`0x1D75CE`), so it stored the
positive overshoot `2` for one update. On the next update, its branch at
`0x1D7576`–`0x1D758A` clamped the height without reducing depth. At frame 3067,
the original SH2 depth was `5577`, while the transplant retained `5737`.
Replacing artwork and pose timing does not require this movement difference.
The corresponding correction should retain SH2's movement, projection,
lifetime and cleanup, while updating the donor pose and shared cache separately.
That separation must not be described as keeping explosions stationary in the
air, since native SH2 itself moves these effects toward the ground.

The private traces, disassemblies, reproduction script and machine-readable
result are under `/tmp/sh-explosion-mod-20261006/airborne`; `analyze.py`
generates `AIRBORNE_CAUSE.json`. The result covers two ordinary enemy
destructions in stage one, not every stage, actor or boss effect.

## Separation of host movement and donor animation

The v0.1.13 candidate implements that separation. Its wrapper first executes
the original SH2 handler, including motion, projection, lifetime and cleanup.
If the native handler marks the object free (`+0x20 = 0xFF`), the wrapper returns
without touching it. For a surviving object, a separate generated routine
updates the donor's shared pose, cache and source-size selection. No SH1 motion
or free-list code is copied into this version.

The visual state machine retains the donor's eleven poses and quotient-based
timing. Its last-pose hold now lasts only while the host object remains alive.
In particular, a short-lived boss particle need not display all eleven poses;
the modification does not prolong its native lifetime or delay boss accounting
to complete the visual sequence.

The candidate with SHA-256
`3b02448a61073b0133c0c40962945eb1b5f1410266f4ce64f51ed6c9611d67ec`
was tested in original and enabled modes for 3,180 steps each. All 34 common
observations of two naturally triggered ordinary explosions matched in world
X, Y, vertical velocity, depth and projected X/Y, including the first airborne
sample and the ground clamp. Both objects appeared and disappeared at the same
sampled frames. The earlier frame-3067 discrepancy is gone: both modes now
report depth `5577` and projected position `(2, 121)`. These are object-state
comparisons, not a claim that the complete rendered images match after changing
the artwork.

A fresh 3,400-step forced-position check also exercised the generated visual
routine. It again produced poses 1–11 at clocks
`891, 892, 896, 900, 904, 908, 912, 916, 920, 924, 928`. All 44 source image
payloads matched their VRAM destinations, and all 17 observed uploads matched
the expected 8,576-byte payload. Creation of the second effect at frame 3090
preserved the current pose-5 cache until the handler restarted it at frame 3092.
Pose 11 remained active through frame 3212, clock 951; unlike the older copied
SH1 handler, the new wrapper then allowed SH2's native lifetime to remove the
object despite the diagnostic keeping its position in view.

The read-only trajectory result is
`/tmp/sh-explosion-mod-20261006/airborne/V13_POSITION_COMPARISON.json`.
The forced-position harness and payload comparisons are under
`/tmp/sh-explosion-followup-20261006/forced`, with the result in
`forced-sh2-reference/RESULT.json`. The public optional-ROM tests additionally
check that all three native SH2 handlers remain byte-identical, that every
wrapper invokes its native handler before the freed-object check and visual
work, and that the 17 hostile-actor/particle initializer changes affect only
their validated method operands. These checks passed with address and undefined
behavior sanitizers; boss progression and wider stage coverage are recorded
separately from this timing reference.

Two additional synthetic comparisons used the later candidate with SHA-256
`a24a64df9057e9140b646994bed75f890e906dd7ebf22e2a97cf56b8cbc27a67`.
An existing object was initialized once with controlled position, velocity,
depth, timer and method, then allowed to run freely. The original particle
handler `0x137AFC` and its wrapper had identical coordinates across 62 samples,
with the same native cleanup event and first freed sample at frame 3119,
timer 30. The tracked-death handler `0x137CF0` and its wrapper matched across
122 samples, including their delay, timer and shared count. Both freed the
object at sample 3179, timer 60, and decremented `0xFF3858` from 7 to 6 exactly
once through the original cleanup instruction.

One particle timer sample was 23 in original mode and 22 in enabled mode at
frame 3103; both were 23 at the next sample. The comparisons therefore do not
claim identical instruction timing or zero CPU cost. Coordinates and the native
cleanup events still matched. These tests enter the steady wrappers directly;
they do not replace the separate first-use boss-initialization and progression
checks. Their private harness and complete result are in
`/tmp/sh-explosion-followup-20261006/isolate/NATIVE_WRAPPER_COMPARISON.json`.
