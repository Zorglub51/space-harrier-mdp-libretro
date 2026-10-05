# Direct MDP CRAM addressing

The addressing fix in version 0.1.4 restores the destination of raster colour
writes. SH1 writes to `0xC00400`, entry 0; SH2 writes to `0xC00462`, entry `0x31`.
The address selects the entry without a game profile or internal game-state check.

## Evidence from the M2 binary

Reference binary SHA-256:
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
The MDP write handler starts at file offset `0xB2CA8`, loaded at `0xC2CA8` in the
Ghidra ELF import used here.

It recognises exactly `0xC00400..0xC004FF`. For an aligned word write, the path
at `0xC2EB2` extracts address bits 1 through 7 (`UBFX` at `0xC2EB8`), then stores
the data word in `CRAM[(address >> 1) & 0x7F]`. The former test of address bit 10
was too broad, and the fixed destination 0 discarded the entry used by SH2.

`tests/fixtures/mdp_cram_m2.json` contains ten synthetic observations produced by
executing original ARM instructions in Ghidra's `PcodeEmulator`. Seven cases
cover entries 0, 1, `0x31`, `0x3F`, `0x40`, `0x7F`, and data word `0xFFFF`.
Three out-of-range addresses stop before ordinary port decoding without a
direct CRAM write. The fixture contains no M2 executable code or game data.

## Scheduling scope

The addressing oracle proves the range, destination and data, independently of
line scheduling. Versions 0.1.4 through 0.1.7 retained the port's existing
`screen().vpos() + 1` scheduling. Version 0.1.8 corrects that origin to
`get_scanline_counter() + 1`, using the same counter as the renderer. See the
[raster timing reference](MDP_RASTER_TIMING.md) for original instruction order,
libretro traces and the remaining timing boundaries.

Pending writes are stored separately for each line and CRAM entry. Several
colours can change during the same HBlank; the last write to the same entry and
line replaces earlier values. Writes outside visible lines are folded into
line 0. Reset clears validity flags, and save states include both queued data
and flags. The queue does not introduce frame averaging or sprite persistence.

## Reproduction

The public test compiles the actual `vdp_mdp_w` method, raster-flush prefix and
array declarations extracted from the distributed patch. Screen position and
renderer scanline counter are independently stubbed, along with ordinary VDP
ports and the observed CRAM destination. Tests cover all 128 destinations,
multiple writes, replacement at the same index, line boundaries, reset and
byte masks passed to ordinary ports.

```sh
python3 -m unittest discover -s tests -p test_mdp_raster_cram.py -v
```

To regenerate the addressing observations, import your binary into a Ghidra ARM
ELF project without analysis and run the supplied script. Adapt the installation
and project paths:

```sh
/path/to/ghidra/support/analyzeHeadless /path/to/projects MdpReference \
  -process m2engage -noanalysis -readOnly \
  -scriptPath scripts/ghidra -postScript MdpCramOracle.java /tmp/mdp-cram-m2.json
MDP_CRAM_ORACLE_JSON=/tmp/mdp-cram-m2.json \
  python3 -m unittest discover -s tests -p test_mdp_raster_cram.py -v
```

The script verifies the binary SHA-256, address mapping and handler entry before
execution. Ghidra can return a zero process status after a script error: check
the final message and generated JSON, then run the test with
`MDP_CRAM_ORACLE_JSON` set.
