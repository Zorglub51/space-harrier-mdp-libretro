# Remaining video-port differences — audit of 0.1.11

This investigation establishes additional differences from the original M2
emulator. It does not change the production core. The palette experiment below
is an isolated diagnostic build, not a release or a complete timing fix.

## Evidence and boundaries

`scripts/ghidra/MdpVideoPortOracle.java` executes the original ARM/Thumb read,
write and byte-access callbacks on synthetic state. The 160 sequences in
`tests/fixtures/mdp_video_ports_m2.json` cover data reads (72), partial commands
(2), status (32), counters (10), other read windows (10), direct VRAM reads (7),
ordinary registers (14), byte register/control writes (6), byte palette writes
(2), and mixed palette access (5).

The script verifies the executable and handler hashes. It uses independent,
deterministically seeded video buffers and a synthetic bus callback for DMA.
There are 258 operations that return normally, 40 that reach the first diagnostic
function, and nine that reach the first diagnostic logging function. Execution
stops at those diagnostic boundaries: their subsequent behavior is not assumed.
The oracle does not execute the renderer, CPU scheduler or complete game.

The original executable SHA-256 is
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
No executable bytes, ROM, captured game memory or game images are published.

Separately, read-only runtime taps examine five deterministic sequences on the
0.1.11 macOS arm64 core, SHA-256
`2d599feb150c90b263db19f0e94ac918805c069b70302aee281ec1a84a106f2b`.
They cover 27,900 frontend frame steps. The first-boss scenario alone holds the
SH2 life counter at nine to reach the transition; its palette is not modified.

## Confirmed palette ordering defect

M2 immediately updates the same palette memory for direct, ordinary-port and
DMA writes. A subsequent read sees the latest write. Synthetic sequences in both
orders establish this independently of render timing.

The port queues a direct write for a later rendering line, but ordinary and DMA
writes update palette memory immediately. An older queued write can consequently
overwrite a newer ordinary or DMA write. A direct write is also invisible to CPU
readback until the queue is consumed.

For example, with synthetic palette entry 49 initially `1111`:

| Sequence | Port before rendering | Port after queued write | M2 |
|---|---|---|---|
| Direct `2222` | `1111` | `2222` | `2222` immediately |
| Direct `2222`, ordinary `4444` | `4444` | `2222` | `4444` remains |
| Direct `2222`, DMA `4444` | `4444` | `2222` | `4444` remains |

The production direct decoder, ordinary write, DMA transfer, readback and render
flush were extracted and executed in a small C++ witness. The surrounding device
services were stubbed. The witness also passes AddressSanitizer and UBSan.

Runtime traces confirm 31 cases in which an older color with different RGB bits
is actually restored after a newer ordinary write. All concern a direct write
queued for line zero during vertical blanking. No overlapping DMA was observed.

| Sequence | Frontend steps | Confirmed older-color restoration |
|---|---:|---:|
| SH1 attract | 6,000 | 14 |
| SH1 scripted gameplay | 6,000 | 7 |
| SH2 attract | 2,400 | 6 |
| SH2 stage 4 reference | 4,500 | 0 |
| SH2 through first boss, diagnostic lives | 9,000 | 4 |

### Isolated visual impact

A private diagnostic build cancels an older queued palette entry when a newer
ordinary or DMA write changes that index. It changes no byte decoding, readback,
CPU scheduling or other rendering behavior. Its SHA-256 is
`34269f077273a6a17adb7731c51c496e1faa339cc904e8ecd649d8a4393c63f3`.

On the SH2 attract sequence, 2,400 frontend calls deliver 2,399 images. Exactly
six images differ: frontend frames 1488, 1548, 1652, 1656, 1660 and 1664. Each
differs only in 640 pixels: the full width of the first two rows, x=0..319 and
y=0..1. Every difference lasts one image; preceding and following images match.
The other 2,393 images match exactly. Both captures reproduce deterministically.
The 1,923,265 stereo sample frames also match exactly, SHA-256
`8c2951fa03ec187f6980125612b537825e2ba2c65373db865313fb2267f525a3`.

This establishes a small, transient sky-color artifact. It does not explain
sprite displacement, and is not a comparison against complete original M2
video. Visual impact in SH1 and the other traced SH2 scenarios remains unmeasured.
Lua trace frame numbers and frontend capture numbers have different origins.

A full correction must also make direct writes immediately visible to CPU
reads while preserving native render-before-CPU ordering. Simply canceling stale
queue entries does not solve that second requirement. If rendering still needs
a delayed state, it must not roll back the CPU-visible palette.

## Other confirmed port contracts

| Access | Original M2 | Current port | Runtime evidence |
|---|---|---|---|
| Direct CRAM byte write | Duplicates the selected byte: `AB` becomes `ABAB`, on either byte address | High lane becomes `AB00`; low lane becomes `00AB` | No such byte writes in the five sequences |
| Direct register byte write | Either byte address writes the register | High-lane writes are ignored | No such byte writes observed |
| Ordinary control byte write | Duplicates the byte before decoding; `8F` becomes `8F8F` | Passes the unexpanded high or low lane | No such byte writes observed |
| Data read with code 4 | Reads CRAM, like code 8 | Reads VSRAM | All 320 observed data reads use code 8 |
| Data read during a partial command | Preserves the first command word | Clears the pending-command flag | No partial-command read observed |
| Ordinary register >10 with register 1 bit 2 clear | Accepts the register write | Inherited Mega Drive mode restriction ignores it | Only register 0/1 initialization occurs in this state in these runs |
| Status read | Returns `0200` plus three mapped internal flag bits | Also forces `3400` and supplies inherited hardware flags | Status is read frequently; the effect depends on which bits the game uses |
| HV counter read | Returns vertical count in the high byte; low byte is zero | Supplies a changing horizontal count in the low byte | The games use this word in both synchronization and random-state code |
| Unsupported read windows/codes | Reaches a native diagnostic boundary | Several windows mirror ordinary ports; code dispatch masks the high bits | No game-visible failure assigned to these invalid accesses |

Status reads preserve partial commands in both implementations. The pending
command difference above applies to data reads, not status reads. Direct VSRAM
byte writes already duplicate the byte correctly in 0.1.11.

The native status formula is
`0200 | ((flags & 1) << 7) | ((flags & 2) << 1) | ((flags & 10) >> 1)`
(hexadecimal constants). Native HV is the low 16 bits of
`(y < -27 ? y + 262 : y) << 8`. These expressions describe the executed handler
contract. Mapping its internal flags and vertical phase to MAME requires
separate scheduler evidence; matching the expression alone is insufficient.

## Counter bits reach the random-state update

The SH2 instruction at `19AC3C` reads `C00008`; the following calculation XORs
the entire word into the state eventually stored at `FF4156`. SH1 has the same
sequence at `1EBBD8`, storing its state at `FF48E6`. The low byte is not masked.
For otherwise identical input state and vertical count, the additional nonzero
horizontal byte necessarily changes the resulting 16-bit random state.

These paths are reached in all five runtime sequences:

| Sequence | Reads in this random-state path |
|---|---:|
| SH1 attract | 434 |
| SH1 scripted gameplay | 250 |
| SH2 attract | 91 |
| SH2 stage 4 reference | 15 |
| SH2 through first boss, diagnostic lives | 88 |

There are 878 calls in total. Of the 51 detailed read examples retained by the
trace sampler, 50 have a nonzero horizontal byte. Those examples are not a
complete census of nonzero bytes. The recorded callback PCs are the subsequent
instructions, `19AC42` and `1EBBDE`.

This is a demonstrated route to game-state divergence, beyond a difference in
an unused register. It does not quantify changed enemy placement or establish
the cause of a particular reported sprite glitch. There has been no controlled
HV-modified core comparison in this audit. The separate synchronization loops
at `19A95A` and `1EB8F6` shift the word right by eight and discard the horizontal
byte; they still depend on the vertical phase.

## Priorities and remaining assumptions

First correct the palette's memory ordering and readback together, with mixed
direct/ordinary/DMA tests, visible-line and blanking coverage, and save/load
replay. Then align byte writes, reads and register decoding with the native
callbacks. Timing-related status/counter changes require a separate controlled
experiment because the games consume these values.

The existing SH1 tree insertion, division guards, shot-counter recovery and
boss-exit recovery remain empirical. This audit found no additional demonstrated
crash in them. In particular, the tree-insertion trampolines have no explicit
attract-mode/variant-81 condition, despite that being the motivating scenario.
Their wider effect still needs original game-state execution evidence before
removal or narrowing.

These findings extend the [fidelity status](FIDELITY_STATUS.md); they do not
invalidate the previously measured renderer matches at identical input state.
They explain why matching the renderer alone does not establish matching game
state or timing.

## Reproduction

Import the private matching ELF into a Ghidra ARM little-endian project, close
the project in the GUI, and execute the checked-in script in read-only mode:

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPO/scripts/ghidra" \
  -postScript MdpVideoPortOracle.java "$OUTPUT_JSON"
```

The checked-in fixture matches the freshly executed oracle output. Its SHA-256
is `035134e7c82c36f88acbb5671eb63eea2cb73139bbc2a39760240a6a41fc3a43`.
The synthetic inputs, per-operation state, memory hashes, changed-byte examples
and diagnostic boundaries are recorded in that fixture. It is an audit reference
for future production regressions, not a claim that the current port passes
all of those contracts.

Runtime traces, the production witness, diagnostic core and screenshots remain
local under `/tmp/sh2-next-20261005`. The prepared source and normal build output
were restored to 0.1.11 after the experiment; the production patch still applies
in reverse without differences.
