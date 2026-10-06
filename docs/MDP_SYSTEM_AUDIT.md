# Reset, loading, interrupts and audio audit — 0.1.11

This follow-up to the [video-port audit](MDP_VIDEO_PORT_AUDIT.md) records further
differences and lifecycle failures. It changes no production code or ROM patch.
All live probes use the 0.1.11 macOS arm64 core with SHA-256
`2d599feb150c90b263db19f0e94ac918805c069b70302aee281ec1a84a106f2b`.
Native evidence uses the same original ELF hash recorded in the earlier audit.

## Reloading content fails while the core library remains loaded

The first load succeeds and runs 600 frontend steps. After `retro_unload_game`,
the second `retro_load_game` returns false in each tested sequence:

| Sequence | First load | Second load |
|---|---|---|
| SH1, unload, SH1 | Success | Failure |
| SH1, unload, deinit/init, SH1 | Success | Failure |
| SH1, unload, deinit/init, SH2 | Success | Failure |

The process and loaded shared library remain the same. Each probe uses isolated
configuration directories and the original local `.smp` files. This is a
Libretro wrapper failure, independent of native M2 fidelity.

`retro_init.cpp` retains the static argument count `ARGUC` and argument array
`ARGUV`. The next command-line parse appends to them. The failed startup logs
contain the launch arguments twice; MAME interprets the second `megadrij` as a
software item and rejects the launch. Calling deinit/init does not clear this
parser state. Frontends that unload the library or restart the process may mask
the failure; these tests do not claim every frontend will expose it.

Reproduce with privately supplied files:

```sh
python3 tests/libretro_reload_regression.py \
  --core /path/to/shmdp_libretro.so --rom /path/to/SH1.smp \
  --second-rom /path/to/SH2.smp --lifecycle deinit-init \
  --frames 600 --output /tmp/reload-result.json
```

Omit `--second-rom` to reload the same game, or choose `--lifecycle same-init`
to retain initialization between loads. The report records explicit load
statuses and stream hashes, never ROM bytes or saved game memory. Exit status
one reproduces the known failure on 0.1.11; this opt-in private-ROM check is not
part of ordinary unittest discovery.

## Reset retains video and sound memory that M2 clears

The native machine dispatcher at `C0B1C` has a reset command `0x102` that calls
the VDP state/reset function `C28D4(vdp, 0)`, sound reset `A7228(sound, 0)` and CPU
reset `95028(cpu, 0)`. This is a logical machine reset path separate from object
construction. Its connection to a particular button in M2's original frontend
has not been established.

Without a supplied state, `C28D4` clears all 64 video registers, selects command
`FF` at address zero, and invokes the backing-store reset for palette RAM,
128 KiB VRAM and VSRAM. The allocation/reset paths establish a zero initial
value for those stores. The sound reset explicitly clears its 8 KiB Z80 RAM.
This reset evidence is instruction analysis, not full native machine execution.

In the port, a real `retro_reset` after 3,000 frames retains all 64 video
registers, both VRAM banks, CRAM and VSRAM byte-for-byte. SH2 also retains the
8 KiB Z80 RAM, including 6,691 nonzero bytes in the measured state. The VDP
command becomes zero instead of `FF`. The direct-palette queue validity flags
are cleared, and the full 128 KiB CPU RAM is cleared. The corresponding native
CPU RAM reset behavior has not been established by this audit.

The probe observes reset before resumed game code can overwrite these areas.
CPU register differences at this observation point are not classified as bugs:
MAME schedules its CPU reset for execution after the notifier. Audio filter
history also survives, but no matching M2 filter-reset contract was established.

The demonstrated consequence is that reset starts with graphics and sound data
from the previous run. A specific resulting visible or audible glitch has not
been attributed to this retention. Correcting it requires reset and save/load
tests separately; clearing memory during save-state restoration would be wrong.

## Half of the ROM padding is left uninitialized

Both original images are padded to a 4 MiB allocation. Native `C0EAC..C0EB8`
passes the full byte count `allocated_size - file_size` to the fill operation,
using byte `FF`.

The inherited `md_slot.cpp` loader computes the pointer in 16-bit words but also
divides the byte count passed to `memset` by two. Both file and software-list
paths have this error. The backing allocation uses `malloc` without clearing.

| Game | File size | Added space | Explicitly filled with `FF` | Left uninitialized |
|---|---:|---:|---:|---:|
| SH1 | `3E0000` | 128 KiB | 64 KiB | 64 KiB |
| SH2 | `380000` | 512 KiB | 256 KiB | 256 KiB |

Sizes in the file-size column are hexadecimal bytes. A compiled witness extracts
the actual size helper and padding expression from the prepared source, starts
with synthetic `A5` memory, and confirms that precisely half the padding retains
that sentinel. Live reads from both loaded games confirm `FFFF` in the first
half and `0000` in the second half on these fresh-process runs. Zero is an
observation here, not a guarantee of what an uninitialized allocation contains.

No runtime read from the padding was observed during 6,000 SH1 attract steps
and 2,400 SH2 attract steps. The read tap is installed after the initial padding
inspection, so that inspection is excluded from the counts. No current gameplay
crash or scene change is attributed to this defect. Nevertheless, a read there
is not guaranteed to match M2 and can depend on allocation history.

## Unacknowledged video interrupts expire differently

`scripts/ghidra/MdpTimingOracle.java` executes original IRQ query/acknowledge,
line-counter and selected frame-loop instructions. The public synthetic fixture
`tests/fixtures/mdp_timing_m2.json` covers 32 query/acknowledge pairs, four
eight-line horizontal-counter sequences, vertical expiration, and two complete
262-slice arithmetic cases. Four native instruction ranges and the ELF identity
are hash-checked. Eighteen invalid acknowledge cases stop at the original
diagnostic boundary; subsequent error behavior is not assumed.

For horizontal interrupts, M2 clears the request on a subsequent decrementing
line even when it was never acknowledged. With register 10 set to one and no
acknowledgement, native IRQ eligibility over eight visible lines is
`0, 4, 0, 4, 0, 4, 0, 4`. Enabling horizontal IRQ on line two therefore does not
deliver the request from line one. The port retains `m_irq4_pending` until
acknowledgement or reset; a later enable can deliver the old request.

For vertical interrupts, M2 clears the unacknowledged request at visible line
zero. The port explicitly retains `m_irq6_pending` at frame end, following an
inherited Mega Drive compatibility choice. A later enable can again deliver a
request that has expired in M2.

These differences are established against native execution. A corresponding
late-enable/masked-IRQ sequence has not yet been demonstrated in SH1 or SH2.
Neither actual native CPU interrupt latency nor its instruction-by-instruction
sampling is executed by this oracle. No specific sprite glitch is attributed to
these pending-flag differences.

The nominal frame budget is not a newly identified frequency bug: M2 uses
262 slices of 3,420 master ticks, consistent with the nominal MAME clock ratio.
The frame arithmetic probes stub CPU results, sound and the VDP line scheduler. They do not
establish equivalence of DMA stalls, HLE costs or full scheduling.

## Byte-write discrepancy also affects direct graphics memory

The earlier direct-CRAM byte issue extends to both direct VRAM banks. The native
CPU byte callback duplicates `AB` into word `ABAB` at each of `D00000`, `D00001`,
`D10000` and `D10001`. This is executed by `MdpVramByteOracle.java` and recorded
in `tests/fixtures/mdp_vram_byte_m2.json`.

A live port probe starts the aligned word at synthetic `1122`. The result is
`AB22` for an even byte address and `11AB` for an odd one: the port merges only
the selected byte. It restores each original word before CPU execution resumes.
The native behavior changes both bytes in the appropriate bank.

No partial-byte direct VRAM writes occur in four distinct traced sequences
totalling 18,900 steps: SH1 attract/scripted, SH2 attract and SH2 stage 4.
All video and audio hashes still match the prior controls with the taps active.
This is an extension of the established byte-normalization defect, not evidence
of another currently visible glitch.

## Audio: concrete option failure, limited default-sound conclusions

The exposed **Sound CPU Overclock %** option does not select this machine's
Z80, whose tag is `:genesis_snd_z80`. The generic Libretro selector only recognizes
other sound-CPU tags. Controlled 100% and 200% runs supply the requested option
but retain clock scale 1.0 and the same 3,579,545 Hz clock, with identical video
and audio over 240 steps. This is an ineffective option; it is not proof of an
audible defect at the default setting.

Native YM access routing and Z80-reset transitions also differ from inherited
MAME behavior. However, no YM or Z80-RAM access is blocked by MAME's bus/reset
guard in 14,400 traced steps. No original-M2 audio waveform comparison was made.
These differences must not be presented as demonstrated missing notes or effects.

The original MDP does have a Z80: construction at `C0CB0` calls `A6F5C`, and the
sound scheduler `A6EAC` executes it in the appropriate state. The live port also
performs millions of Z80-originated YM writes. An earlier private assumption that
MDP had no Z80 is unsupported and must not guide an audio rewrite.

## Reproduction and next corrections

For either native oracle, use the imported matching ELF in a closed Ghidra
project and run the public script in read-only mode:

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPO/scripts/ghidra" \
  -postScript MdpTimingOracle.java "$OUTPUT_JSON"
```

Substitute `MdpVramByteOracle.java` for the direct-byte reference. The checked-in
fixtures match fresh executions of both public scripts. No original executable,
ROM bytes, captured game memory or game pixels are included.

Private live probes, native disassembly and the padding witness are retained
under `/tmp/sh2-more-20261005`. Fix reload/parser state and deterministic ROM
padding independently from reset and IRQ semantics. Reset requires explicit
initial-state coverage; IRQ changes require delayed-enable and game traces.
The earlier palette/readback and counter findings remain outstanding.
