# SH2 ranking font: missing direct VRAM writes

The ranking title and initials were corrupted because the game could not replace
its font through the direct VRAM window. This is separate from the raster colour
and line-phase corrections in 0.1.4.

## Evidence

The M2 write handler at file offset `0xB2CA8` accepts `D00000..D1FFFF` as a
128 KiB VRAM window. Its path at loaded address `0xC2D62` writes a 16-bit word
to the VRAM pointer using `((address - D00000) >> 1) & FFFF`. The binary is
the same SHA-256-pinned private reference as the other native audits.

SH2's ranking sequence clears its font through guest `0x18ECAC`, then calls
`0x190FAC` with successive row counts to reveal it over eight passes. The source
is the complete font at ROM `0x1ABB3C`; the destination is `D0D400..D0DFDF`,
the 95 tiles starting at `6A0`. A trace of the unchanged 0.1.4 core observes
13,680 word writes: 95 glyphs × 8 rows × 2 words × (one clear + eight passes).
The final bus data matches all 3,040 bytes of the intended font.

Despite those writes, the actual VRAM at `D400..DFDF` still matched the older
font at ROM `0x1AAF3C`. That font only supplies a subset of the letters used by
the other screens. The CPU map exposed only `D00000..D0001F` as VDP ports;
the font destination was unmapped.

The previous palette-2 workaround remapped `C6xx` attributes to bank `4xx`.
It concealed some missing writes: the top score's initials used palette 2,
while the broken ranking title and other initials used palette 0 (`86xx`).
M2's tile renderers at loaded addresses `0xC1430` and `0xC1BC0` select the tile
using the eleven low attribute bits independently of palette.

## Correction

The lower window `D00000..D0FFFF` now uses the existing direct VRAM accessors.
They combine byte enables and invalidate the graphics caches when a word is
written. `D10000..D1FFFF` remains the separate upper bank used by the current
MDP renderer; it must not wrap onto the lower bank.

The palette-dependent font remap is removed. The game now supplies the font
and its reveal animation itself, without a ROM font swap or per-frame overlay.
The legacy cartridge-profile output remains in the adapter API but no longer
changes tile selection.

## Validation and remaining work

The public test compiles the direct accessors and write implementation from the
distributed patch, checking readback, byte enables and all six glyph caches.
Private headless captures cover the title, gameplay, first boss, stage selection,
Yees Land and ranking. The ranking glyphs are now legible; SH2 audio remains
identical over the compared sequences. Both complete SH1 video/audio streams
remain unchanged over 6,000 attract frames and 6,000 scripted frames.

The remaining scenery behind the ranking is a separate scaler activation issue.
M2's extended plane registers and full rendering/timing equivalence still need
to be implemented and validated. This correction does not assert that the
entire SH2 renderer is faithful or that every stage has been tested.
