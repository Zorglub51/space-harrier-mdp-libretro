# Mark VI: SH1 sprite presentation and 120 Hz

Version 0.1.22 adds `mame_sh1_rendering`: `original` (default), `mark_vi`
(native refresh) and `mark_vi_120` (experimental interpolation). SH2 retains its
separate option. The cartridge loader authenticates the supported game before
its profile selects a preference; changing SH2's setting cannot enable SH1's
mode or enable the enhancement for an unrelated cartridge.

The SH1 constructor is translated in `src/markv/sh1_markvi.h`. It shares the
host sprite record, pixel renderer, producer lifecycle and interpolation with
[SH2 Mark VI](SH2_MARK_VI.md). Existing VDP method names beginning with
`sh2_markvi_` now dispatch construction by the authenticated game profile.
Original (M2) continues to use the native renderer and its display limits.

## SH1 construction before quotas

The reference is SH1's native 68000 constructor at `1702EC..172504`, not a
substitution of SH1 addresses into the SH2 algorithm. It traverses the sorted
object chain at `FF40B8`, following links at object offset `+18`, then reads
22-byte pose descriptors and 12-byte piece records. The tile allocation table
is `FF3D16`. The host list contains each piece's coordinates, attributes and
zoom directly, removing the native 40/80-entry partition budgets and seven-bit
transform/index limit. Alignment, valid object range and cycle detection remain
structural checks; they are not sprite-count quotas.

Native signed arithmetic and rounding, tile increments, palette/bank selection,
flip variants and body-before-shadow traversal are retained. Two SH1-specific
rules require a separate emitter:

- Mirrored assemblies use different attribute masks for their two halves. The
  first uses `(flags << 11) & C000`; the second uses the native Y-flip bit plus
  horizontal flip, `((flags << 11) & 1000) | 0800`, before palette/tile additions.
  Both scaled (`170C64/170D4C`) and unscaled (`171E9E/171F3C`) paths apply this.
- Scaled tile grids cache projected X coordinates from their first row and reuse
  those columns for subsequent rows. Computing every row's X independently
  disagrees with the native constructor when its piece offsets differ. The host
  uses a dynamic row cache instead of inheriting the native stack capacity.

Shadows use SH1's own tables: ground projection at `3C63E2` with `FF40A2/FF40A4`,
LOD factor table at `3C7104`, reciprocal table at `3C6904`, fixed descriptor
`1304` and scaled descriptors beginning at `12EE`. The body object's projected
height does not replace its shadow's ground projection.

The [visibility audit](SH1_MARK_VI_AUDIT.md) identifies six live handlers whose
bit `0080` only removes nearby segments to reduce display load. Mark VI removes
that recorded budget from body and shadow emission decisions, preserving the
independent no-shadow bit `0004`. It does not modify guest flags or recompute
visibility from later coordinates. Hidden/deleted poses, retiring handlers,
Harrier's deliberate blinking and verified structural hiding remain active.

## Observe construction without changing execution

The two read observers run only for the authenticated SH1 cartridge and ignore
reads performed with side effects disabled. They leave bus data unchanged.

| Event | Observed data address | Required emulated PC |
| --- | --- | --- |
| Constructor entry | `FF40B8..FF40B9` | `17034A` or `17047C` |
| Constructor completion | `FF3CA4..FF3CA5` | `17083C` |

Entry is the native read of the sorted object-list head. It captures the full
128 KiB of work RAM before quotas alter the native output. Completion is the
data read performed by `MOVE.L FF3CA4,D1` at `170836`, immediately before
retirement-list cleanup. That read also occurs when the object chain is empty.

An opcode read at `170836` is not an equivalent completion signal: the 68000 can
prefetch it while the reported PC still belongs to a distant branch. Checking
only a nearby PC range can miss completion, while treating every opcode fetch
as completion can authenticate an unfinished producer. Observing the actual
data read with PC `17083C` ties the event to execution of the instruction.

## Producer banks, uploads and clears

`src/markv/sh_markvi_profile.h` supplies the per-game addresses to the shared
lifecycle. SH1 uses:

| Field | SH1 address |
| --- | --- |
| Producer selector, low bit | `FF1BE0` |
| Bank 0 head pointer | longword at `FF1210` |
| Bank 1 head | `FF1EC8` |
| Bank 0 overflow / count | `FF16DC` / `FF195C` |
| Bank 1 overflow / count | `FF195E` / `FF1BDE` |

Each producer has its own entry snapshot. Completion records the native
80-entry head geometry and overflow geometry/count, masking link bytes that the
game subsequently repairs. A matching complete SAT DMA promotes that producer's
snapshot to the displayed generation; construction alone does not advance the
presentation. The host list is then rebuilt from that immutable snapshot.

Later overflow uploads keep the displayed complete host list only when source,
count, destination, stride, geometry and the untouched SAT prefix match. As in
SH2 since 0.1.20, authentication can use either the displayed overflow signature
or the next completed generation of the same producer. This handles a faster
emulated CPU without replacing displayed geometry before the next full head
upload. Unknown writes, incompatible uploads and scene clears invalidate the
active list. An empty completed list replaces the old picture; no previous-frame
sprite pixels are retained.

The existing three RAM snapshots, producer signatures, history and pending
presentation buffers were already serialized in 0.1.21. SH1 support adds no
serialized fields and leaves that state layout unchanged. The profile is derived
from the immutable loaded cartridge and reapplied on reset; it is not guest save
state. Variable host lists are rebuilt after loading. States from before 0.1.21
remain incompatible. Matching visual replay requires the same rendering and
screen-format options.

## Shared clipping correction in 0.1.22

Mark VI previously discarded a horizontally shrunken source cell when its
projected span was less than eight pixels and crossed screen X = 0. This could
remove visible edge pixels, including inside the extended 16:9 field where the
former 4:3 edge is no longer the viewport boundary.

The shared Mark VI rasterizer now samples the cell normally and clips individual
output pixels to the active viewport. This correction applies to SH1 and SH2,
both horizontal orientations, 4:3 and 16:9, and both Mark VI refresh modes.
It does not change the Original (M2) pixel path. The production renderer test
covers a half-width cell crossing X = 0, its full-width counterpart, both game
profiles, mirrored output and both viewport widths.

## Optional 120 Hz presentation

SH1 uses the existing two-presentation clock at twice the native NTSC refresh,
approximately 119.845 Hz. Two `retro_run` calls execute one native emulation
refresh; the second presents queued video and PCM without executing another
CPU update or polling game input. PCM is split without resampling. The accepted
frontend cadence is separate from the requested per-game setting; a pending
half is completed before negotiating a change, and a rejected change retains
the previous cadence.

Interpolation matches object address, handler, pose/LOD descriptor and piece,
including mirror/shadow identity. It interpolates position and zoom across the
measured object-update interval, clamping at the endpoint. New/deleted pieces,
pose changes and discontinuous motion do not revive an old picture. Background
animation and sprite artwork changes retain their native cadence. Interpolation
adds approximately one object-update interval of visual delay, often 17–33 ms;
collision positions and game speed remain native. No CPU overclock is required.

## Constructor evidence and limits

The constructor analysis produced two distinct comparisons against the frozen
0.1.21 core executing SH1's reconstructed native 68000 code. These are native
68000 constructor measurements, not an independent execution of M2's original
ARM emulator and not final full-core gameplay validation.

- **96 controlled cases / 288 records:** synthetic object, descriptor and piece
  data are supplied to the native constructor. Cases cover both producer banks,
  Deflicker OFF/ON1/ON2, all eight assembly flags, scaled/unscaled emission and
  negative offsets. Deliberately different row offsets expose the first-row X
  cache. All measured records match the host output as multisets, with no extra
  host records. The numeric fixture and provenance hashes are published in
  `tests/fixtures/sh1_markvi_emitter_native.json`; no game artwork is included.
- **83 paired gameplay captures / 5,158 native records:** constructor entry and
  completion RAM were sampled during a 7,000-frame scripted SH1 run. All recorded
  native pieces match host records after decoding the native zoom index and
  masking link bits. The host produces 15 additional pieces excluded by native
  quotas, reaching 94 pieces in the largest captured list. This sample exercises
  both banks but only assembly flags 0 and 1.

Those counts come from the constructor analysis's controlled native fixture and
private `native-comparison.json` report. Record comparisons preserve duplicate
counts but do not prove ordering, final pixels, every intended hidden piece or
all stages. ROMs and RAM captures remain private. Full-core video, audio,
CPU/RAM and save-state results are recorded in [the 0.1.22 validation report](SH1_MARK_VI_VALIDATION.json).

## Overflow upload interrupting the next constructor

At native CPU speed, a large SH1 sprite group can keep the constructor running
across an interrupt. The interrupt uploads the previous overflow count while
the same producer bank's tail RAM is already being rewritten. Comparing those
partially updated bytes with completed tail snapshots incorrectly disabled
Mark VI for one refresh. In an unpaused stage-1 run with rapid-fire inputs and
nine maintained lives, all 39 inactive refreshes between frames 6,200 and 12,900
had this cause; the displayed head prefix was unchanged in every case.

The optional renderer now retains its already complete displayed list for this
specific SH1 case. Acceptance requires the exact native overflow caller
(`0F4B0C` for bank 0 or `0F49D6` for bank 1), an observed in-progress constructor
for that same bank, an active presentation, the active tail's original count,
matching source/destination, normal VRAM DMA mode/increment, and an unchanged
head prefix. The partial producer snapshot is never promoted. Other callers,
wrong counts/banks, modified head prefixes, completed producers with unexpected
edits and scene clears retain their existing rejection behavior. SH2 keeps its
previous completed-tail checks. This addresses interruption at native CPU
speed without requiring an overclock or changing the game's DMA/RAM writes.

## Full-core validation for 0.1.22

The [hash-only report](SH1_MARK_VI_VALIDATION.json) covers 34 runtime cases on
macOS arm64: 12 rendering/option comparisons, opening sequences for all 18
stages, and four longer sequences starting from stages 1, 5, 7 and 18. Each
long sequence runs 13,000 native refreshes, with two presented at double rate.
All 10,301 monitored gameplay refreshes per long run retain the extended list.
Full PCM and sampled RAM/68000 state match the corresponding Original runs.
Save/replay, pending half-frame states, option changes, frontend refusal, worker
threads, 4:3/16:9, native Deflicker variants and 100%/400% CPU settings are covered.

The original test inputs inherited extra SH2 Start presses that paused some SH1
scenes; those preliminary results are excluded from the stage sweep and longer
sequence results above. The final SH1 stage input starts once, checks the native
pause byte, requires changing frames and uses repeated fire button presses.
The optional remaining-lives precondition prevents game over without changing
boss health, collision handling, object state or RNG. This is targeted coverage,
not a claim of complete playthroughs or proof of every possible frame.
