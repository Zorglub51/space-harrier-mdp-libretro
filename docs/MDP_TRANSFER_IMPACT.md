# Runtime impact of the MDP transfer corrections

The tested candidate preserves the complete video and PCM streams over 16,500
frame steps compared with version 0.1.10. This is bounded runtime coverage, not a
claim that every transfer path or game scene has been exercised. The separate
[native transfer oracle](MDP_TRANSFERS.md) covers synthetic boundary cases.

The exact baseline core SHA-256 is
`6bfb822a2d7a258c437aa3496a832f774fac82c00d8e5c45c71ddced8f16a641`.
The tested candidate SHA-256 is
`79876f432b3af2ec2205c464c20fb48af83fe7180166e4ac1d13690fbee7b38b`.

| Scenario | Frame steps | DMA commands | Sampled transfers | Video / PCM |
|---|---:|---:|---:|---|
| SH1 attract | 3,000 | 2,709 | 15 | Both identical |
| SH2 stage 4 | 4,500 | 3,092 | 15 | Both identical |
| SH2 stage 1 through the first boss | 9,000 | 5,362 | 21 | Both identical |

The last scenario maintains the BCD life counter at `FF1170 = 09` after frame
2600 to avoid game over. It does not alter objects, stage state or video state.
The other scenarios use ordinary deterministic inputs or no input.

## What the games actually transfer

The traces contain 11,112 CPU-to-VRAM transfers and 51 CPU-to-CRAM transfers.
No CPU-to-VSRAM DMA or VRAM-copy command appears in these runs. All observed
CRAM transfers start at address zero. The 51 sampled transfers include the
actual source words and before/after video memory; their destination banks
match the established native aligned-transfer contract with zero differing
bytes. This comparison uses captured source data, rather than a new ARM oracle
execution on each game snapshot.

Every one of the 11,163 DMA commands explicitly rewrites all three source
registers, 21 through 23, before starting. Consequently, the old source-register
updates cannot affect the following DMA in this coverage. The candidate
preserves these source registers after all 11,163 transfers. Of the sources,
581 are in ROM and 10,582 are in the upper 64 KiB of RAM at `FFxxxx`; none is in
the lower RAM half.

Ordinary VSRAM data writes occur 1,037 times in SH1 and 1,770 times in each SH2
scenario. Direct writes to `C00200..C0027F` and unsupported non-fill DMA data
writes occur zero times. Per-write VSRAM values were not retained, but the
snapshots contain nonzero `FFD8` and, in SH2, `FFF5`. The candidate mirrors entries
0 and 1 into entries 62 and 63. This changes 24 of the 51 VSRAM snapshots relative
to the baseline while the compared video streams remain identical; no further
causal attribution is made from these samples.

After-state is observed at the next VDP callback or frame notifier. Other CPU
writes can update upper MDP memory during that interval, so the isolated DMA
memory comparison concerns its destination bank, not every unrelated bank.

## RAM mapping, reset and save/load

A separate synthetic integration probe confirms independent lower and upper
64 KiB RAM banks: `FE0000` and `FF0000` no longer alias. All 32 tested mirrors
from `E0xxxx` through `FFxxxx` select the expected bank. The version 0.1.10
baseline exposes only 65,536 bytes and fails this bank-independence check.

Both candidate banks retain distinct patterns through serialization and
restoration, byte for byte. Reset clears all 131,072 bytes. The probe writes its
save patterns in pre-save callbacks without advancing CPU time, writes the
reset pattern immediately before device reset, and restores the original
serialized machine state after testing. Serialized state size increases from
9,153,908 to 9,219,444 bytes, exactly the additional 65,536 bytes of RAM.

These results precede the later direct-VSRAM byte-lane correction. That path had
zero runtime hits in all three scenarios, and these measurements should not be
presented as execution coverage of that additional correction.

## Final core validation

The final macOS arm64 core SHA-256 is
`2d599feb150c90b263db19f0e94ac918805c069b70302aee281ec1a84a106f2b`.
It includes the subsequent byte-write correction, which is tested against
original byte-handler execution with synthetic memory.

Four complete replays compare this final core with 0.1.10: SH1 attract and
scripted input (6,000 frames each), SH2 attract (6,000), and SH2 stage-1 scripted
input (9,000). All 27,000 frames retain identical video and PCM stream hashes.
Save/load reproduces all 180 subsequent frames and audio in each game's control
window. These are final-artifact checks, distinct from the earlier traced runs.

All 96 automated tests pass with fresh original-execution references and private
ROMs. The eleven DMA/bus tests also pass address and undefined-behavior sanitizers.
The public fixtures contain 111 video-port sequences and 38 bus cases. Tests
cover the relevant production paths, not every I/O branch represented by M2.
