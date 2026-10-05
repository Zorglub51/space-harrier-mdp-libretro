# MDP plane and sprite geometry

Version 0.1.6 replaces table-content guesses with M2's explicit video registers.
The core remains a targeted MAME integration; this is not a complete rewrite of
M2 or a claim of complete rendering/timing equivalence.

## Why SH2's sprites appeared too low

The old SH2 background renderer subtracted 53 lines from the start of perspective
and stretched the remaining table entries to the bottom of the screen. Sprite
coordinates were not transformed the same way. In deterministic stage 4 footage,
the first perspective entry at line 166 was displayed at line 113. In the stage 1
trace, entry 157 was displayed at 104. This moved the ground relative to the
objects. No corresponding adjustment exists in the native M2 renderer.

M2's scanline caller at loaded ARM address `C3314` subtracts the vertical blank
interval from its frame counter. `C334A` passes the resulting visible line to
`C1E24`; that value reaches plane renderer `C1BC0` unchanged. Its instruction at
`C1C64` selects the 16-byte table entry for that same line. The framebuffer's
separate eight-line border affects its destination address, not the transform
index. Addresses here refer to the pinned ELF import; subtract `10000` for file
offsets.

## Explicit registers and transforms

The native write handler at `C2CA8` recognises `C00100..C0017F`. It stores the low
byte at register `(address-C00100)/2`. The port now retains all 64 registers and
serializes them; those writes no longer alias ordinary VDP ports. The native
word-write decoder is executed by `scripts/ghidra/MdpRegisterOracle.java` against
68 synthetic cases. Byte-enable handling is tested separately as MAME integration.

Registers 32 and 33 (`C00140`, `C00142`) describe plane A and B respectively:

- bit 7 enables transformation;
- bits 0–4 select its table in 128 KiB VRAM, in 4 KiB units;
- bit 5 chooses one 16-byte entry per displayed line, otherwise one affine entry;
- bit 6 wraps source coordinates; when clear, coordinates clamp to the edges.

An entry contains signed 4.12 horizontal and vertical steps, and signed 20.12
origins. The affine path also adds the screen line and destination start offset;
the per-line path uses the stored origin directly. Both source axes advance for
each output pixel. Plane dimensions come from register 16, using M2's shift table
`{5,6,0,7}`. Tile attributes determine palette, flips and priority. Source Y=0 is a
valid coordinate, not an inactive-line marker. Coordinates outside the formerly
assumed 224..511 workshop remain valid after wrapping or clamping.

The new renderer composes each transformed plane in its ordinary plane position,
retaining the window and sprite priority stages. It removes the 53-line offset,
perspective stretching, special mountain/ceiling cutoffs, equal-plane-base test,
and guessed table activation. A nonempty old table no longer activates a plane
whose register is disabled. The public plane test executes the distributed C++
method against synthetic pixels produced by Ghidra's original ARM execution.

## Sprite geometry

Register 36 (`C00148`) independently enables sprite zoom with bit 7 and selects
its table with bits 0–4. SH1 writes `9F` (table `D1F000`); SH2 writes `91`
(table `D11000`). This also works on title screens where there is no active
perspective table from which to infer the bank.

SAT X bits 9–15 select a 16-byte entry. Both scale values are masked to 15 bits,
but only X is capped at `1000`. Y may enlarge a sprite. The native height is
`height_in_tiles * (scale_y >> 6) >> 3`. A zero height is invisible. The selected
row uses a ten-bit circular difference `(scanline + 128 - SAT_Y) & 3FF`, followed
by the native fixed-point source-row division and optional vertical flip.
Previously Y was capped like X, zero entries fell back to full size, tiny sprites
were forced to one line, and the SAT Y coordinate used a nine-bit mask.

These contracts are checked against original sprite geometry instructions,
separately from tests of the shrink and tile decoding helpers. They do not prove
equivalence of the entire sprite compositing pipeline.

## Validation scope

Native observations are derived from private `m2engage`, SHA-256
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
Public fixtures contain synthetic inputs and outputs, no ROM or M2 code.

Headless comparisons cover SH2 stages 1, 3 and 4, title/attract mode and ranking,
and the existing SH1 attraction and scripted sequences. The geometry corrections
also affect SH1 where the former Y limit or guessed transform differed from M2;
SH1 video is therefore not asserted to be bit-identical to 0.1.5. The final core passes 61 automated tests and replays 39,020 frames across these
six scenarios. Every compared audio stream matches 0.1.5 exactly. This is a
non-regression check of game execution, not a full-frame M2 pixel oracle.

This work adds no persistence or smoothing. Remaining work includes M2 timing,
full sprite composition and extended palette selection, screen-edge clipping,
and wider gameplay validation. Existing save states are incompatible with the
expanded video register state; start from the original cartridge image.
