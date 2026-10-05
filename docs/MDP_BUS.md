# MDP CPU bus reference

The MDP bus has 128 KiB of CPU RAM. Its word callbacks select RAM before applying
an address mask, including when a DMA source cursor crosses `0xFFFFFF`. These
rules are separate from the 128 KiB of video RAM documented elsewhere.

## Original callbacks and executable evidence

`scripts/ghidra/MdpBusOracle.java` executes the original Thumb read16 callback at
`0xC0F74` and write16 callback at `0xC086C` through their native returns. The
constructor resolves these callback addresses at `0xC0CC6` and `0xC0CC4`;
`0x94DC4` stores them in the bus interface, and `0xC2A00` attaches that interface
to the VDP. The script verifies both the private ELF SHA256 and the loaded bytes
of each callback. It replaces no instructions or callback functions.

`tests/fixtures/mdp_bus_m2.json` contains 38 synthetic cases: 30 word reads and
eight word writes, with readbacks and complete RAM hashes. The RAM seed operates
on word indices, making the two 64 KiB banks distinct. For example, the original
callback returns `0x5678` at `0xFE0000`, `0xD678` at `0xFF0000`, and `0x5678` at
`0x1000000`. ROM address zero contains `0x1234` in the same fixture.

The fixture includes ROM and RAM branches only. It does not establish complete
I/O decoding, cartridge behavior, instruction-fetch mapping, bus timing or
interrupt equivalence. Some synthetic ROM-size inputs deliberately bypass the
loader's power-of-two invariant to measure the callback's mask expression.
They do not describe an actual cartridge loaded by M2.

## RAM selection, mirrors and boundary crossing

Both callbacks first test the unsigned address against `0xE00000`. At or above
that boundary they access the numeric 16-bit word:

```text
ram[(address >> 1) & 0xffff]
```

`0xC0FCA`–`0xC0FD4` performs the read; `0xC08B6`–`0xC08C0` performs the write.
They therefore use 65,536 words, or 128 KiB. The allocation and CPU-memory
registration agree with this size: the machine requests `0x10000` elements of
its word type and registers `0x20000` bytes at `0xC0BFC`–`0xC0C20`.

The portable mapping covers `0xE00000`–`0xE1FFFF`, mirrored with mask `0x1E0000`.
The byte callbacks agree: read8 at `0xC095E`–`0xC096A` and write8 at
`0xC0A48`–`0xC0A54` use backing byte offset `(address & 0x1FFFF) ^ 1`
after the same unsigned RAM-boundary test. This is static instruction evidence;
the 38-case bus fixture executes the word callbacks. The byte-lane exchange is
consistent with big-endian CPU accesses to numeric little-endian RAM words.

Consequently `0xFE0000` and `0xFF0000` address different halves. Reset clears the
whole allocated RAM share. This is a change to the SH1/SH2 core's machine map;
it must not be presented as proof of compatibility with arbitrary Mega Drive
software. The enlarged state backing also changes save-state layout.

For DMA reads, the adapter normalizes addresses at or above `0xE00000` to:

```text
0xe00000 | (source & 0x1fffe)
```

It then uses the emulated bus. This preserves the native RAM selection at
`0x1000000`; simply masking the source to 24 bits would select ROM instead.
Word alignment in this adapter also matches the native RAM callback. DMA source
addresses are even by construction. The word-callback oracle does not establish
68000 address-error behavior for a guest instruction accessing an odd address.

## ROM selection and profile checksum

For addresses below `0x400000`, the native reader uses:

```text
rom[(address & (allocated_rom_size - 1)) >> 1]
```

The loader at `0xC0E78`–`0xC0EBC` rounds the allocation up to a power of two and
pads unused bytes with `0xFF`. The bus oracle measures the reader; it does not
execute the complete file loader or prove the portable cartridge mapper.

The VDP profile identifier is not a CRC. At `0xC0EC0`–`0xC0ED8`, M2 adds the
8,192 big-endian 32-bit values in the first `0x8000` ROM bytes, modulo `2^32`.
`0xC0EF0` calls the setter at `0xC2AF0`, which stores that sum at VDP offset `0x54`.
The original private ROMs yield:

| Game | Native profile sum |
| --- | --- |
| SH1 | `0x51244898` |
| SH2 | `0x7EE5D3D9` |

Neither matches the unrelated exceptions `0x4F967B9E` and `0xCA196D58`, which
permit a normal VRAM data write while code `0x21` is selected, or `0x0EDEB52C`,
which permits the corresponding VSRAM case at code `0x25`. For SH1/SH2, rejecting
those unsupported data writes follows the native profile behavior. The native
fill case, selected separately by command code and register 23, remains valid.
The transfer fixture exercises both the rejected default case and the two VRAM
exceptions; the portable core supports the two Space Harrier profiles, not all
of M2's game-specific exceptions.

## Direct VSRAM byte writes

The native byte-write callback at `0xC09E4` routes VDP accesses through
`0xC0A76`–`0xC0A86`. It aligns the address and duplicates the byte into both lanes
before calling the word handler at `0xC2CA8`. Thus byte `0xAB` written to either
lane of a direct VSRAM word becomes numeric word `0xABAB`. Two additional
transfer-oracle cases execute the original byte callback and
word handler together, confirming the result for an even and an odd address.
Their checked byte-callback hash is recorded in `mdp_transfer_m2.json`.
The portable direct VSRAM path normalizes the incoming byte lane before updating
memory.

Direct VSRAM writes at `0xC00200`–`0xC0027F` use the shifted native layout and
mirrors described in [MDP_TRANSFERS.md](MDP_TRANSFERS.md). They do not modify the
selected VDP command, address or pending state. Native reads do not decode this
window symmetrically: the read handler falls through to ordinary port decoding.
No direct VSRAM read feature should be inferred from the write window.

## Reproduction

With the matching private ELF imported into an ARM little-endian Ghidra project:

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPO/scripts/ghidra" \
  -postScript MdpBusOracle.java "$OUTPUT_JSON"
```

The fixture and script contain synthetic memory and hashes only. Neither the
private emulator binary nor game data is distributed with them.
