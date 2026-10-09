# MDP raster CRAM scheduling

Direct CRAM writes are queued for the next **VDP render-counter line**, using
`get_scanline_counter() + 1`. A target outside visible lines 0..223 is mapped to
line 0. This fixes the coordinate system used by the queue; it does not claim
complete CPU-cycle timing equivalence with M2.

## Confirmed coordinate error

The v0.1.7 queue used `screen().vpos()`, while
`render_videoline_to_videobuffer()` is called with `get_scanline_counter()`.
These counters differ in MAME's standard Mega Drive timing mode. The VDP
counter starts at 0 when the screen enters VBlank at beam line 224, so the
render counter is 38 lines ahead of the beam modulo 262.

A trace of the released macOS ARM64 Libretro core, SHA-256
`4ae0fc219d041232b185832a6f513729f44aedd5c168e40d91ff54f0029fa665`,
measured 678 SH2 CRAM writes across six consecutive gameplay frames. Every
write had `(render_counter - beam_position) % 262 == 38`. The internal counter
was read from MAME's saved item; the beam was derived independently from
`screen.time_until_pos(0, 0)` and the frame period. Reads of the VDP HV register
also confirmed the internal counter during visible lines.

| Render counter | Screen beam | Previous queue target | Corrected target |
| ---: | ---: | ---: | ---: |
| 1 | 225 | 0 | 2 |
| 39 | 1 | 2 | 40 |
| 223 | 185 | 186 | 0 |
| 226 | 188 | 189 | 0 |

Using the beam could collapse multiple early-line writes into one line 0 value
and schedule later writes for a line that had already been rendered. The fix
uses the same counter for enqueueing and consuming writes. It retains the
next-line delay, per-index last-write rule, and VBlank mapping.

## Native ordering evidence

Reference executable SHA-256:
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
Addresses below are loaded Ghidra addresses; code file offsets are 0x10000 lower.

The frame loop at `C0644` executes 262 native line slices. At `C0700` it calls
`C32C8/C3314`, which updates the VDP and renders the line. Only afterwards does
`C0722` call the 68000 execution function. Visible line 0 corresponds to native
slice 38. Direct CRAM writes in `C2CA8` update memory immediately, but CPU writes
after one render are naturally consumed by the next render.

`scripts/ghidra/MdpLineClockOracle.java` executes the original frame-loop region
`C06FC..C0754`, the original line scheduler, and the original CRAM write handler.
It replaces each CPU slice with one synthetic write through that native handler;
sound processing and pixel drawing are intercepted. The four observed slices
cover visible lines -1, 0, 1, 2. Their event order is always render, CPU-slice write,
completed CRAM write. Each following render sees the preceding slice's value.
The script checks that order and memory values before exporting
`tests/fixtures/mdp_line_clock_m2.json`.

This is an execution oracle for ordering, not an emulation of the 68000 engine,
its native hooks, interrupt latency, or DMA cycle costs. It does not prove that
all game writes occur in identical slices in M2 and the port. In particular,
the relative order of direct CRAM writes, ordinary port writes and DMA still
needs broader timing coverage. No temporal averaging or sprite persistence is
introduced by this correction.

The later [SH1 sky investigation](SH1_SKY_DITHERING.md) executes the actual M2
68000 engine, original guest sky routines and this frame loop together. It
reproduces the sampled title/high-score sky phases with an isolated workload;
it does not validate complete gameplay scheduling.

## Reproduction

Import the local reference executable as ARM ELF without analysis, then run:

```sh
/path/to/ghidra/support/analyzeHeadless /path/to/projects MdpReference \
  -process m2engage -noanalysis -readOnly -scriptPath scripts/ghidra \
  -postScript MdpLineClockOracle.java /tmp/mdp-line-clock.json
MDP_LINE_CLOCK_ORACLE_JSON=/tmp/mdp-line-clock.json \
  python3 -m unittest discover -s tests -p test_mdp_raster_cram.py -v
```

The tests compile the distributed queue and flush methods. Their fake screen
beam and VDP render counter are independent, covering visible-line scheduling,
wraparound, VBlank, and the observed native write/render order. The synthetic
fixture contains no executable or game data.
