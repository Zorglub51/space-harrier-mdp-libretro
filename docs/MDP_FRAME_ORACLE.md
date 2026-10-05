# Native M2 indexed frame oracle

`scripts/ghidra/MdpFrameOracle.java` executes the original ARM Thumb renderer
at `C1E24` against captured video memory. It executes the original plane and
sprite helpers and their composition; it does not render from decompiled C.
The only intercepted external call is `memset` at `265E8`.

Execution stops at `C1E5C`, after indexed composition and before the NEON palette
conversion. This oracle proves palette indices and normal/shadow selection. It
does not by itself prove frontend RGB, audio, raster scheduling, game logic, or
all scenes. `MdpColourOracle.java` covers the separate native colour conversion.
No binary, ROM, captured game pixels or game memory are included in the repository.

## Reproduce

Import your own `m2engage` ELF into a Ghidra project at its original addresses,
without analysis. The script checks SHA256
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`
and the ELF mapping `file B1E24 -> VA C1E24`.

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPOSITORY/scripts/ghidra" \
  -postScript MdpFrameOracle.java "$SNAPSHOT_DIR" "$OUTPUT_DIR" all
```

Replace `all` with `166` or a comma-separated list such as `8,10,22` to select
visible lines. A fourth script argument, `after`, selects the post-render upper
VRAM snapshot for a paired mutation check. The default is `before`.

Use one process per Ghidra project: even a read-only project is locked while a
script runs. Java 21 and Ghidra 12.1 DEV were used for the recorded observations.

## Snapshot contract

A capture directory contains these files for each visible line `NNN`, padded to
three decimal digits. Every word is stored as its numeric **little-endian** value.
The script validates each file size and records its SHA256 in the output.

| File | Bytes | Meaning |
|---|---:|---|
| `line-NNN-before-m_vram.bin` | 65536 | Lower VRAM, `D00000..D0FFFF` |
| `line-NNN-before-m_mdp_ram.bin` | 65536 | Upper VRAM, `D10000..D1FFFF` |
| `line-NNN-after-m_mdp_ram.bin` | 65536 | Required only with the `after` argument |
| `line-NNN-before-m_regs.bin` | 128 | 64 register words; low byte of each is used |
| `line-NNN-before-m_vsram.bin` | 128 | MAME's 64 VSRAM words |
| `line-NNN-after-m_cram.bin` | 256 | 128 CRAM words after pending raster writes |

M2 stores two extra leading VSRAM words: its ordinary VSRAM port writes at
`((address + 4) & 0x7f) >> 1` and mirrors the first two values into words 0/1.
The adapter shifts MAME's words by two with wrap, then initializes these mirrors.
It assumes no later access at `7C/7E` has overwritten those mirrors. A trace that
uses such accesses needs a write-history-based adapter; a final MAME array alone
cannot recover their ordering.

A snapshot is evidence for a core line only when its timing is established.
The audited capture observes the scanline counter before the render timer,
reads the inputs, then captures the output two emulated microseconds later.
The timer runs one microsecond after the counter increments. Compare input
buffers before and after; detect writes to registers, VRAM, upper VRAM, VSRAM
and SAT. CRAM may legitimately change when queued raster writes are applied.
Before/after equality cannot exclude a write followed by an identical restore
inside that interval. For a changed upper-VRAM word, replay both inputs and
verify that the original renderer produces identical pixels, or obtain a more
precise capture. Do not equate an arbitrary end-of-frame dump with every line's
rendering state.

## Native ABI and outputs

The context receives CRAM, contiguous 128 KiB VRAM, VSRAM and the 64 byte registers.
Fields `60/64/68/6C` follow the original line-clock initialization: framebuffer
width 474, height 240, active width 320 when `(reg12 & 81) == 81`, otherwise 256,
and active height 224. The renderer receives a visible line number without an
extra vertical bias. The original caller places that line at framebuffer row
`line + 8`.

`line-L-indices.bin` has 474 bytes. Crop from `(474 - active_width) / 2` for
`active_width` pixels: x=77 in H40, x=109 in H32. Bits 0..6 select CRAM entry
0..127; bit7 selects normal rather than shadow intensity. Intermediate native
plane and sprite words are also saved where the display path is active.
`line-L.json` records the instruction count, native boundary, dimensions,
input hashes and selected upper-VRAM snapshot. `run.json` marks a complete
visible frame only when all 224 lines were captured in that invocation.

Native composition uses these words:

- Plane: priority `8000`, normal intensity `80`, colour in bits 0..6.
- Sprite: priority `8000` plus `80` when high priority, colour in bits 0..6;
  zero means transparent.

A nontransparent sprite wins when its word is at least the plane priority bit.
With shadow enabled, sprite colour `3E` toggles the plane's intensity bit;
`3F` clears it. The test `sprite & 3E` also applies to the upper palette bank.
`MdpCompositeOracle.java` and `test_mdp_composite.py` compare 208 synthetic
original-ARM cases with the compositor compiled directly from the public patch.

## Measured correction

On a synchronized SH2 stage-4 frame from the earlier core, 70,958 of 71,680
indexed pixels matched. All 722 differences occupied the player shadow at
lines 209..223: the inherited compositor selected highlight while M2 selected
shadow. Sprite-layer colour values matched on all 224 lines. Eight captured
lines had one upper-VRAM word change during the capture interval; replaying
both snapshots produced identical original output on all eight.

Additional sampled SH1 lines exposed three pixels at the left edge. The native
`C1084` helper drops a reduced cell whose starting x is negative, even when its
right edge would be visible. The ordinary eight-pixel cell instead clips its
visible suffix. `test_mdp_sprites.py` compiles the actual patch's clipping guard
and reduction lookup and checks both cases against original ARM output.

After the compositor and clipping corrections, the candidate core
`4ae0fc219d041232b185832a6f513729f44aedd5c168e40d91ff54f0029fa665`
matched all **82,240 measured indexed pixels**: one complete SH2 stage-4 frame
and eleven lines each from SH2 stages 1/3 and SH1. All renderer input hashes
matched the inputs used by the original ARM execution; sprite layers also
matched. [MDP_FRAME_VALIDATION.json](MDP_FRAME_VALIDATION.json) records the exact
line coverage, input-manifest hashes and native/candidate output hashes without
including game pixels. These observations do not establish every game's scene,
frontend RGB or timing behavior.
