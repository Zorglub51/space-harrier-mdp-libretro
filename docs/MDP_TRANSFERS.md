# MDP video transfers: native reference and implemented scope

The MDP fill, CPU-to-video DMA and VRAM copy paths follow measured original M2
memory and command-state behavior. Direct and ordinary VSRAM writes share the
native wrapping and mirrors. The RAM source window has two distinct 64 KiB
banks. These corrections do not establish complete port, CPU or video timing
equivalence. The ordinary Mega Drive transfer routines remain separate.

## Executable reference

`scripts/ghidra/MdpTransferOracle.java` executes the original ARM/Thumb handler at
loaded address `0xC2CA8` (ELF file offset `0xB2CA8`). It checks the private ELF's
recorded SHA256 and independently checks the loaded handler bytes before execution:

- ELF: `2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
- Handler plus its literal pool, 1,568 bytes:
  `d07969110e42a6830564247764dfe5d780dc9205cf52036ceb18a5147bc2a55d`.

The script does not modify the imported program. Inputs are synthetic VRAM,
CRAM, VSRAM, registers and port writes. The only replacement callback supplies
synthetic CPU bus reads. A valid write runs through the native return; an invalid
write stops when it reaches the native diagnostic function at `0x9E818`, without
assuming that this function returns.

`tests/fixtures/mdp_transfer_m2.json` contains 111 sequences:

| Group | Sequences | Coverage |
| --- | ---: | --- |
| Fill | 36 | Zero and nonzero lengths, even and odd destinations, wrapping, increments 0/1/2/255, different data bytes, command-pending states, DMA-enable clear, and writes after completion |
| Invalid fill modes | 2 | Primed CRAM/VSRAM fill codes reach the diagnostic boundary before writing memory |
| CPU-to-VDP DMA | 36 | VRAM/CRAM/VSRAM, zero and large lengths, source/destination wrapping, alignment diagnostics and DMA-enable states |
| VRAM copy | 18 | Zero and large lengths, overlapping regions, source/destination wrapping, increments and a subsequent data write |
| Command state | 6 | Register writes, interrupted commands, invalid alignment and a register write between fill setup and data |
| Additional dispatch | 5 | Copy/fill type and command combinations, including invalid commands |
| VSRAM writes | 3 | Ordinary and direct writes, low-word mirrors and later mirror overrides |
| Profile-dependent data writes | 3 | Default diagnostic and two unrelated title exceptions; only the default applies to SH1/SH2 |
| CPU byte writes to VSRAM | 2 | Original byte and word handlers executed together, both byte lanes |

Each sequence records every executed port write, command state, all 64 registers,
complete memory SHA256 hashes, changed-byte counts and synthetic bus-read traces.
Memory hashes use numeric little-endian storage; native VSRAM uses M2's shifted
backing layout. The fixture describes the deterministic seed and callback
formulas. It contains no game ROM, captured game memory or rendered game pixels.

## Implemented fill contract

Native code at `0xC2E2C` first clears command-pending bit 3. It selects fill from
`(code & 0x30) == 0x20` and `(register[23] & 0xC0) == 0x80`, independently of a
separate fill-pending latch. Code `0x21` is the valid VRAM fill case.

At `0xC2F36`–`0xC2F8E`:

1. Read the 16-bit length from registers 19/20. Zero represents `0x10000` here.
2. Round the number of high-byte writes to an even count: `(length + 1) & ~1`.
3. Write the low byte once at native backing byte offset `address ^ 1`.
4. Write the high byte at backing byte offset `address`, then advance by register
   15 after each write, wrapping the destination at 16 bits.
5. Store the final address and set the command code to `0xFF`. Preserve the
   length and source registers.

The byte-offset description above uses M2's numeric little-endian VRAM backing;
it must be converted when accessing a host's array of numeric 16-bit words.
Both odd and even fill destinations are supported. Increments of zero are
meaningful. Writes remain in the lower 64 KiB of the 128 KiB MDP VRAM space.

With zero length, address zero, increment one and zero data, the lower 64 KiB is
cleared and the address returns to zero. The upper 64 KiB remains unchanged.
Runtime traces observed this request at SH2 guest PC `0x19E672` and SH1 guest PC
`0x1EF60E`. The inherited fill path previously performed only one high-byte write
for this request, leaving stale VRAM contents. The fixture reproduces this exact
parameter combination using synthetic memory.

Native register writes at `0xC3072`–`0xC307A` change the selected register without
resetting the current address or command code. The MDP control path preserves
those two fields, including when an autoincrement register write occurs between
fill setup and its data word. The standard Mega Drive behavior stays unchanged.

`tests/test_mdp_transfers.py` compiles the production fill method and relevant
port routing extracted from the public MAME patch, then compares their memory
and state against the native fixture. This exercises production code rather
than a second fill implementation used as an expected result.

## Version 0.1.10 integration checks

The tested macOS arm64 core has SHA256
`6bfb822a2d7a258c437aa3496a832f774fac82c00d8e5c45c71ddced8f16a641`.
All 84 automated tests pass with private ROMs and fresh native reference outputs.
The new fill tests compile the complete production fill method, its data-port
dispatch prefix and the register-write fragment. They check both values of the
inherited fill-pending latch, full 128 KiB VRAM hashes, CRAM/VSRAM, all registers,
post-fill writes and separation from ordinary Mega Drive routing. Other control
port execution, native diagnostic machinery and DMA/copy paths are outside that
C++ probe.

Runtime traces cover 86 SH1 fills over 6,000 attract frames and 53 SH2 fills over
2,400 attract frames. All 139 preserve length/source registers and finish with
code `0xFF` and no pending fill. Seven complete before/after VRAM snapshots
confirm the zero-length clear: five start with nonempty memory and two already
contain zeros. Each ends with all 65,536 lower-bank bytes zero. An eighth clear
has state-only coverage because the capture's snapshot limit was reached.
Post-write state is observed at the next VDP access or frame boundary; this is
an integration trace, not an atomic native execution oracle.

Four control sequences total 27,000 frames: SH1 attract and scripted input
(6,000 each), SH2 scripted input (9,000), and SH2 attract (6,000). Audio is
identical to 0.1.9 throughout. All 226 sampled screenshot checkpoints match,
but the full video streams differ. An additional per-frame comparison of both
attract runs identifies exactly these RGB changes:

| Game | Frontend frame | Changed pixels | Effect |
| --- | ---: | ---: | --- |
| SH1 | 268, 4340 | 534 each | Clears red/grey logo fragments during a black transition |
| SH1 | 4352 | 45 | Clears a small black fragment during title-image loading |
| SH2 | 266, 4708 | 534 each | Clears red/blue logo fragments during a black transition |
| SH2 | 1479, 5921 | 256 each | Clears the brown left part of a temporary top-row tile pattern |

Every change lasts exactly one frame; the preceding and following images match
byte for byte. All other frames match in these two runs (5,999 available video
callbacks per game). SH2's green right-hand tile pattern remains in both versions
and needs separate investigation. These checks establish bounded regression
coverage; the original handler's memory contract, rather than visual preference,
is the basis for the correction.

## Implemented DMA, copy and VSRAM contracts

Version 0.1.11 implements these additional contracts:

- Native CPU-to-VDP DMA takes an unsigned 16-bit **word count**. Zero transfers no
  words; `0x8000` and `0xFFFF` transfer 32,768 and 65,535 words. The previous
  implementation first converts to a 16-bit byte count, which can truncate these
  lengths and treats a resulting zero differently.
- Native DMA clears length registers 19/20 but preserves source registers 21–23.
  It does not gate the transfer on register 1's DMA-enable bit. The source
  addresses passed to its callback can cross `0xFFFFFF`. The original bus
  callback still selects 128 KiB RAM after this boundary; the port preserves
  that selection before handing the read to MAME's 24-bit address space. See
  [the bus reference](MDP_BUS.md) for the separate callback evidence.
- Native DMA writes only the low 16 bits of the read callback result. Destination
  addresses wrap at 16 bits. Odd word destinations reach diagnostics; their
  behavior after the diagnostic is deliberately not modeled by this oracle.
  The bus read precedes the alignment check. Earlier writes remain, while the
  address and length registers retain their initial values on that boundary.
- Native CRAM DMA wraps across 128 words. VSRAM DMA wraps in its 128-byte backing
  and applies the native shifted layout and mirror writes. It does not stop
  simply because the destination reaches byte address `0x80`.
- Native VRAM copy is a sequential byte copy, so overlapping writes affect later
  reads. Zero length copies no bytes. It preserves length/source registers and
  finishes with code `0xFF`.
- Command setup tests register 23 bit 7: when set, code `0x21` only prepares
  data access and code `0x30` copies, even when bit 6 is clear. Other combinations
  reach diagnostics. The later data write selects fill only for type `0x80`.
- The direct write window `C00200..C0027F` updates VSRAM without changing the
  selected command or its address. Ordinary writes and DMA use the same memory
  helper. In MAME's logical layout, writing word 0/1 also updates word 62/63;
  writing 62/63 later does not change 0/1. Native storage is a rotation by two
  words. CPU byte writes to the direct window duplicate the byte onto both lanes.

`tests/test_mdp_dma.py` extracts the distributed transfer methods and MDP
dispatch, using a synthetic bus callback with an exact read trace. It compares
all memory banks and register state with the native reference. This separates
transfer semantics from the independently checked bus-address adapter.

The full-frame oracle now rotates VSRAM storage without manufacturing mirror
values. This prevents the reference adapter from hiding an incorrect write.

## Remaining boundaries

These synthetic measurements do not establish transfer timing, CPU stalls,
interrupt timing, reads from VDP ports, or equivalence of every game scene.
A diagnostic-boundary match does not claim equivalent error reporting or abort
behavior. The existing VRAM DMA pause remains an explicitly unproved scheduler
integration choice. Direct CRAM writes are queued while ordinary writes and DMA
are immediate; mixed-write ordering still needs correction and validation.
Mode-dependent register restrictions and VDP reads also remain outside this
change. This must not be described as a complete native VDP port implementation.

## Reproduction

Import the private, matching ELF into a Ghidra ARM little-endian project. With
that project closed in the GUI, run the script in read-only headless mode:

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPO/scripts/ghidra" \
  -postScript MdpTransferOracle.java "$OUTPUT_JSON"
```

The script writes only the requested synthetic JSON output. No private reference
binary is distributed with the repository.

Run the public fill regression and optionally compare a freshly generated oracle:

```sh
python3 -m unittest discover -s tests -p test_mdp_transfers.py -v
MDP_TRANSFER_ORACLE_JSON=/path/to/output.json \
  python3 -m unittest discover -s tests -p test_mdp_transfers.py -v
```
