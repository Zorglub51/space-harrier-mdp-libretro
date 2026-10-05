# SH2 hook reconstruction audit

The review of the v0.1.9 reconstruction (`6a00a8a87b66b08f10d7392678f196d2b6561854`)
found no further incorrect restored SH2 opcode. The 119 addresses in M2's SH2
native-hook table match the 119 addresses in `rompatch/patch.py`'s `SH2` list.
This establishes coverage of the table, not semantic correctness by itself.

The 77 entries whose existing explanation cites SH1 or symmetry were checked
against their **own SH2 ARM handler**. The restored operation, memory direction,
operand width/register, and unchanged extension words agree with that code. The
review did not assume that a similar SH1 routine proves the SH2 replacement.

Examples of independently checked cases:

| SH2 address | Restored instruction | Evidence in its SH2 handler |
| --- | --- | --- |
| `18BD94` | `MOVE.W (A1),(A0)` | Read through A1, then write through A0; no post-increment in this instruction. |
| `18BD3C`, `18BD7C`, `18BDD4` | `MOVE.L D1,(A3/A3/A2)` | Long stores to the corresponding line-table destination. |
| `13C2AC` | `ADDI.W #$80,D1` | Explicit addition to D1's low word, followed by the intact store through A2. |
| `13BF9E` | `ASR.L #7,D1` | Arithmetic shift by seven before construction of the sprite attribute. |
| `178F1A` | `MOVE.B $FF3884,D0` | Read from byte FF3885 in word-swapped host storage, representing guest FF3884. |
| `1A2DB6` | `MOVE.B D1,(A0)+` | Byte store through A0 followed by increment. |
| `1A4A7E` | `MOVE.B (A2)+,(A1)+` | Byte read through A2 and store through A1, with both pointers incremented. |

The `18BDC0` handler reads only the low word of the long at FF3538 before
masking the result with 15. This is equivalent to the reconstructed long
addition followed by that mask; the optimized native load does not justify
changing the guest instruction's width.

## What this establishes

This is a static reconstruction audit. It does not establish complete
equivalence of all blocks, condition codes, interrupts, or execution timing.
Some handlers combine several guest instructions or specialize their operation
for game invariants, so the first native memory access need not belong to the
restored first guest instruction.

Executable native comparisons are separate evidence. In particular,
`scripts/ghidra/Sh2LineOracle.java` and `Sh2TilemapOracle.java`, their synthetic
fixtures, and the corresponding tests validate their specific blocks and
cases. Their case counts must not be presented as exhaustive validation of all
119 hooks. The tilemap oracle supports the v0.1.9 correction at `190A80`:
`MOVE.W (A0)+,D6`, replacing a mistaken store through A0.

For further coverage, prioritize complete projection and object-list blocks
such as `13CAD6`, `13CACC`, and `13BF46`. Compare native execution and the
repaired 68000 sequence from captured legal game states, including every D/A
register, CCR/X, memory accesses, and the next guest PC. Arbitrary synthetic
states that violate a native specialization are useful diagnostics but do not
alone demonstrate a gameplay defect.

The reviewed native executable has SHA-256
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
The original SH2 input has SHA-1
`80f576af01d6413c0b92073e2f947b0431f12a74`.
Neither game data nor native executable code is included in this document.
