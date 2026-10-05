# SH2 pre-boss lightning: reconstructed tilemap read

Version 0.1.9 corrects one reconstructed 68000 instruction used to draw the
lightning animation before SH2 bosses. The previous instruction wrote to the
source address instead of loading a tile word. The following addition then
accumulated stale values, selecting unrelated graphics and palette attributes.

## Original M2 contract

Guest PC `0x190A80` is handled by the original ARM block at file offset
`0xBE9AC`, loaded address `0xCE9AC`. The reference executable SHA-256 is
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.

The block reads one word through the guest bus at A0, adds D1's low word and
writes the 16-bit result to A1. D6 receives the result in its low word, with
its upper word preserved. A0 and A1 advance by two. The final comparison of
D0 with the updated A0 determines whether execution returns to `190A80` or
continues at `190A8A`. NZVC comes from that comparison; X comes from the addition.
The native dispatcher advances by 36 or 34 ticks respectively. Those dispatcher
increments are not a claim about complete 68000 cycle equivalence.

The original block performs no memory write to the source. This identifies the
reconstructed sequence:

```asm
190A80: MOVE.W (A0)+,D6   ; opcode 3C18, replacing the incorrect 30C1
190A82: ADD.W  D1,D6
190A84: MOVE.W D6,(A1)+
190A86: CMP.L  A0,D0
190A88: BNE.B  190A80
```

Only the first instruction changes. SH1's repair table and the shared renderer
are unchanged.

## Runtime evidence

The bug reproduces without buttons, cheats or RAM changes in SH2's attract
sequence, before Trimuller in stage 13. In the recorded run, the corrupt
animation spans frontend frames 1657 through 1704. The copy routine emits
12 batches of 800 tilemap words, starting at direct VRAM address `D0E080`.
All 9,600 writes in 0.1.8 differ from the required source-word-plus-D1 value.
The first four are `C639, 863A, 463B, 063C`, instead of `C001` for these empty
source tiles. The wrong values select tiles throughout the 0..2047 range and
alternate palette attributes, explaining the visible text fragments.

With `3C18`, all 9,600 captured writes match the source word plus D1. The runtime
ROM is identical before and after the animation, and all audio samples match
the 0.1.8 run over 1,801 frames. The lightning graphics are visible again.
Frame numbers identify this deterministic capture, not a universal frontend
clock or a guarantee that every boss has been exercised.

## Validation boundary

The native block is executed on 76 synthetic inputs, including register upper
halves, arithmetic flags, address wraparound and both dispatch exits. The public
fixture contains only synthetic inputs and observed outputs, without original
executable or game data. The portable reference checks the complete block's
contract; the production core runs the repaired 68000 instruction through MAME.
Runtime bus comparisons check that production path on the actual animation.

A second capture reaches the stage-1 boss in a scripted game. Its 9,600 tilemap
writes also match the source and attributes exactly. Only the life counter is
maintained at nine for that diagnostic run; no stage, object or VDP state is
modified. The unmodified attract run remains the primary reproduction.
Across the 301 attract screenshots from frame 1500 through 1800, only the
48 animation frames differ from 0.1.8. All 79 automated tests pass with fresh
native references and the private original ROMs.

Separately, two SH1 scenarios totaling 12,000 frames and the existing 9,000-frame
SH2 stage-1 control sequence retain exactly the same video and audio as 0.1.8.
That SH2 control sequence ends before its boss; the attract capture supplies
the actual regression coverage for the reported transition.

These results establish this tilemap reconstruction fix. Other game hooks,
complete CPU/video timing and all-stage pixel equivalence remain separate work.

## Reproduction

The reference is `src/markv/sh2_tilemap_hook.h`, tested against
`tests/fixtures/sh2_tilemap_m2.json`. To regenerate the native observations,
import the reference ELF in Ghidra without analysis, then run:

```sh
/path/to/ghidra/support/analyzeHeadless /path/to/projects MdpReference \
  -process m2engage -noanalysis -readOnly -scriptPath scripts/ghidra \
  -postScript Sh2TilemapOracle.java /tmp/sh2-tilemap-m2.json
SH2_TILEMAP_ORACLE_JSON=/tmp/sh2-tilemap-m2.json \
  python3 -m unittest discover -s tests -p test_sh2_tilemap_hook.py -v
```

The script checks the executable identity and stops before the original
dispatcher branch. Guest bus callbacks supply synthetic data and record the
ordered accesses. It does not require, contain or distribute the game ROM.
