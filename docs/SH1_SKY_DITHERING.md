# SH1 sky colour alternation and vertical shimmer

Investigation: 2026-10-09, released 0.1.22 macOS arm64 core. This is a diagnosis,
not a claim that shimmer has been fixed. No production renderer, ROM patch,
shader or installed core is changed by this audit.

Follow-up: an isolated execution of the **original M2 CPU**, line scheduler and
SH1 sky routines now reproduces both sky phases. All 54,228 sampled port pixels
also match this native-execution reference. This establishes the source of the
sampled sky alternation more strongly than reading the ROM alone. It does not
establish full-game timing or the final output of the complete M2 application.

## Reproduced result

The title screen alternates sky colours between consecutive native frames.
The high-score screen after the stage-3 attract demo also alternates the vertical
positions of some colour transitions by two source pixels. These effects exist
in raw 320x224 libretro output, before frontend scaling, overlays and shaders.

The sampled sky pixels match the two variants in the original ROM exactly:

| Scene and mode | Captures | Sky sample | Mismatched pixels |
| --- | ---: | --- | ---: |
| Scores, Original, CPU 400% | 121 | x=4, y=0..143 | 0 |
| Scores, Mark VI 120 Hz, CPU 400% | 241 | x=4, y=0..143 | 0 |
| Title, Original, default CPU | 21 | x=160, y=108..127 | 0 |
| Title, Original, CPU 400% | 21 | x=160, y=108..127 | 0 |
| Title, Mark VI native rate, CPU 400% | 21 | x=160, y=108..127 | 0 |
| Title, Mark VI 120 Hz, CPU 400% | 42 | x=160, y=108..127 | 0 |

Total: 467 raw captures, 54,228 checked sky pixels. Both variants occur in every
sequence. These are selected unobstructed columns, not comparisons of complete
frames. Title rows 105..106 are deliberately excluded: the logo covers them in
part of the default-CPU sequence. Different CPU settings need not advance the
logo animation at identical frontend frame numbers.

A negative control shifts one score image down by one pixel. Neither expected
phase matches: each comparison finds 22 incorrect rows. The check does not
accept arbitrary vertical movement or align the captured rows to obtain a pass.

## Why the boundaries move

SH1 stores two four-bit palette indices in each sky-table byte. The routine at
guest PC `142B2E` increments the phase word at `FF406C`. It selects the low or
high nibble at `142B88..142BF0`, writes the initial backdrop colour through
`C00400`, and selects the corresponding generated horizontal-interrupt program.
The paths beginning at `142BFC` and the table builder at `142CD2` use the same
two-variant arrangement. These instructions/data are in the original ROM;
the observation is not derived from an invented colour smoother.

For the captured score scene, the first relevant transition is at row 74 in one
variant and row 76 in the other. The following transitions are at 78/80 and
82/84. These positions occur in the ROM's palette-index sequences themselves.
The port's captured rows have the same positions. Thus the two-pixel movement
in this sample does not require an extra interrupt-timing error to explain it.

At title pixel (160,112), the two source CRAM values are `08A8` and `0A8A`.
The native colour contract gives RGB (136,170,136) and (170,136,170). Their
average would be (153,153,153), but emitting that constant colour would be an
additional operation, not the raw palette value emitted on either frame.

The selected RAM snapshot supplies `FF4060` (palette pointer), `FF4064`
(packed-index table pointer), and the signed words `FF4068`/`FF406A` (offsets).
For these stable scene samples, source row selection is `offset + scroll + y/2`,
using integer division. Reading each nibble from the original ROM independently
predicts both captured variants. No screenshot is used to construct the expected
colours or to estimate a vertical correction.

## Native M2 evidence and limits

Reference executable SHA-256:
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
Core under test SHA-256:
`5f79ffca39cbfbfbacef0e8c942e7019714bbd5151db6da7958641e16b9603e7`.

Previously executed original ARM oracles establish render-before-CPU ordering,
the R10 horizontal-interrupt counter, and the RGB conversion. See
[raster timing](MDP_RASTER_TIMING.md), `mdp_timing_m2.json`, and
`mdp_colours_m2.json`. Original `C3314` reloads the counter at visible line zero;
with R10=1, the horizontal request occurs every second visible line. Original
`C1E24` and registered colormap `229E08` produce normal RGB components `34*c`.

### Original CPU execution

An r2 trace of machine constructor `C0C78` resolves its CPU name to `m68k_3`.
The registered factory is `668E0`, the relocated vtable is `431D44`, and its
execution method is `66750`, reached through wrapper `95018`. The executor
queries the VDP interrupt level once at the beginning of a CPU slice, compares
it with the 68000 interrupt mask, acknowledges an eligible interrupt and enters
the guest vector with a 44-cycle initial cost. It then dispatches original
68000 instructions through its opcode table. This is a different boundary from
the port's inherited delayed interrupt timers.

`scripts/ghidra/Sh1SkyCpuOracle.java` executes these original ARM instructions
with Ghidra's PcodeEmulator. It runs the original CPU constructor and opcode-table
builder, loads the authenticated SH1 ROM, and maps the captured scene RAM using
M2's numeric little-endian word storage. It then:

1. Rebuilds palette immediates with original guest code `142D22..142D80`.
2. Runs original sky updater `142B2E` for each input phase, including the phase
   increment and self-modification of the RAM interrupt program.
3. Runs the original 262-slice frame loop `C06FC..C0754`, original VDP scheduler,
   original CPU executor, IRQ query/acknowledgement and original CRAM handler.
4. Records CRAM at each native pixel-renderer entry. Every case renders the
   expected 232 lines (-8..223) and performs 112 sky writes on lines 1,3,..223.

The high-score test reproduces transitions at 74/76, 78/80 and 82/84. The title
test reproduces the alternating `08A8`/`0A8A` colour at row 112. Across both
phases of both scenes, the harness performs 5,521,646 execution steps, including
host-service interceptions. All 467 sampled core captures match the resulting
native CRAM phases: **zero differences in 54,228 unobstructed sky pixels**.
The one-pixel-shift negative control fails against both native phases, with 22
incorrect rows each. Malformed identity, row, write and phase records are rejected.

The test boundary is deliberate: scene state and IRQ instruction scaffolds
come from a captured RAM snapshot; palette immediates are regenerated by the
original CPU. A synthetic idle loop replaces the rest of the guest workload.
V interrupts, game accelerators, sound, pixel composition and presentation are
outside this experiment. Allocation and memory-copy services are intercepted;
CPU instructions, the line clock, horizontal IRQs and palette writes are not.
No launcher resources are needed for this emulation test.

Thus the tested two-pixel sky movement can be produced by M2's actual emulation
code and is not evidence, by itself, of an extra vertical shift in our port.
This is **not a recording of the complete original M2 application**, nor a claim
that every line in a full game frame or its perceived intensity is identical.

In particular, the 467 captures above are **from this libretro port**, not from
the original m2engage application. They must never be presented as proof that
the final original high-score screen visibly vibrates in the same way.

Known differences in pending-IRQ expiry and mixed CRAM-write ordering remain
separate audit findings. A private timing experiment did not eliminate the
alternation and changed the game's attract progression. It was reverted and
not installed or published. Those changes cannot honestly be described as a fix
for this reported sky movement.

Removing this reproduced source alternation would be an enhancement unless
further evidence identifies an original M2 operation that suppresses it.
Such an enhancement should leave Original mode intact and should not be called
a pixel-perfect M2 correction.

## Recheck private captures

`tests/sh1_sky_check.py` verifies the original ROM identity and compares a
selected sky column against both phases. To use the original CPU reference,
generate a private report (no binary, ROM, RAM or artwork is exported):

```sh
/path/to/ghidra/support/analyzeHeadless /path/to/project SH1Collision \
  -process m2engage -noanalysis -readOnly -scriptPath scripts/ghidra \
  -postScript Sh1SkyCpuOracle.java /tmp/native-sky.json \
  /path/to/jp_jp_space_harrier.smp /path/to/sky-ram.bin
```

Add `--native-oracle /tmp/native-sky.json` to the capture-check command below.
The report's binary, ROM and RAM identities must match the supplied inputs.
Without that argument the check only uses the ROM-data model. Both modes reject
missing frames, invalid RAM/pointers, non-native image sizes and any pixel
outside both predictions.
It requires Pillow and private inputs; no ROM, captured RAM or artwork is
included in this repository.

```sh
python3 tests/sh1_sky_check.py \
  --rom /path/to/jp_jp_space_harrier.smp \
  --ram /path/to/sky-ram.bin \
  --captures /path/to/original-scores \
  --first 7750 --last 7870 --x 4 --top 0 --bottom 144 \
  --report /tmp/sh1-sky-result.json
```

The RAM input is exactly 64 KiB, `FF0000..FFFFFF`, in guest big-endian byte order,
captured during the same stable scene. PNGs are consecutive raw frontend outputs
named `full-NNNNN.png`. Frame numbers above belong to this attract run, not a
general guarantee about every input history. Check that the selected region is
unobstructed and the scene parameters are unchanged throughout the sample.
