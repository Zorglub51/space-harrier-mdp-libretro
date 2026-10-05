# SH2 native execution reference

## Corrected line-phase reset

SH2 guest PC `0x18BCF4` must contain `2204` (`MOVE.L D4,D1`). The previous
`4E71` (`NOP`) reconstruction omitted an observable write in the original
m2engage Thumb handler at file offset `0x0BF174` (table entry `0x0BF175`).
The pinned private binary SHA256 is:

```text
2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f
```

The original ARM loads D4 from CPU-state offset `0x38` at file `0x0BF17E`
and stores the full 32-bit value to D1 at offset `0x2C` at `0x0BF206`.
No intact instruction after the hook performs this copy.

This is part of the line-table generator at `0x18BB94`. At `0x18BCCE`, the
guest sets D4 to -32. Each iteration writes `(D1 + 0x170) << 12` into its
MDP line record, increments D1 at `0x18BCF0`, and branches over the reset
while D1 is negative. Once D1 reaches zero, the missing instruction resets
it to -32. NOP allowed the phase to continue increasing instead. The routine
has several callers, including `0x178F42` and `0x178FDA`; the correction is
not specific to a collision or one boss. Runtime frequency and visual impact
must be measured separately from this block-level proof.

## Original ARM oracle and portable comparison

`scripts/ghidra/Sh2LineOracle.java` executes original ARM bytes in Ghidra's
`PcodeEmulator`. It verifies the binary SHA256, locates the handler by file
offset, checks both terminal `BX r3` instructions, and stops before their
dispatch after verifying the restored stack and dispatcher target.

The 33 synthetic cases cover both exits, comparison equality, signed
overflow, register upper halves, D0 wraparound, address wraparound and
dispatcher-counter wraparound. The normal fixture contains inputs and
measured outputs only, without ROM or original executable bytes.

The observed block contract is:

- D1 receives all 32 bits of D4; D4 survives.
- A0 advances by 16 and D0 by one, with 32-bit wraparound.
- A3 receives the long at guest `0xFF116A`; A2 receives A3 minus 64.
- NZVC reflects `CMP.L A2,D0`. M2's separate X byte contains the complete
  flags snapshot of the preceding `ADDQ.L #1,D0`; its low bit is X.
- The signed less-than exit resumes at `0x18BCD0`, adding 64 to the
  dispatcher counter; the other exit resumes at `0x18BD0A`, adding 62.

`src/markv/sh2_hooks.h` is an independent portable reference of this block,
following the SH1 test arrangement. It is not installed in MAME: the core
continues to execute the repaired 68000 opcode. Its test compares every
recorded output and checks unrelated-register preservation. A separate
assertion locks the adapter opcode to `2204`. This is not a differential
execution test of the complete MAME 68000 core.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -p test_sh2_native_hook.py -v
```

To regenerate with Ghidra 12.1 and Java 21, set `GHIDRA_HOME`, `JAVA_HOME`
and `M2ENGAGE_BIN` to local installations and the original private binary:

```sh
oracle_dir="$(mktemp -d)"
mkdir -p "$oracle_dir/project" "$oracle_dir/config" "$oracle_dir/cache"
XDG_CONFIG_HOME="$oracle_dir/config" XDG_CACHE_HOME="$oracle_dir/cache" \
  "$GHIDRA_HOME/support/analyzeHeadless" \
  "$oracle_dir/project" SH2Line \
  -import "$M2ENGAGE_BIN" -noanalysis \
  -scriptPath "$PWD/scripts/ghidra" \
  -postScript Sh2LineOracle.java "$oracle_dir/original-arm.json" \
  -log "$oracle_dir/ghidra.log"
SH2_ORACLE_JSON="$oracle_dir/original-arm.json" \
  python3 -m unittest discover -s tests -p test_sh2_native_hook.py -v
```

Ghidra is an emulation implementation, not original hardware. Full renderer,
interrupt and scheduler equivalence remain outside this proof. No SH1/SH2
hook equivalence was assumed to obtain the replacement instruction.

## Division guard remains a compatibility exception

`SH2_DIVZERO_GUARD` at guest `0x13D35C` skips averaging when a processed list
has no accepted objects. It is not proven equivalent to original M2 division
by zero. Moreover, an initially empty list branches from `0x13D22C` to
`0x13D41C`: that separate path explicitly passes two zero arguments to
`__divsi3` at `0x13D424`, bypassing the guard entirely. These instructions
and the division helper have no SH2 HLE entrypoints in the filtered table.

This audit records that reachable structural gap without changing it.
Establishing M2's actual divide-by-zero semantics is necessary before a
faithfulness correction; extending the existing bypass alone would remain
a compatibility workaround.
