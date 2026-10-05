# SH1 native execution reference

Development starts with Space Harrier I. The long-term target is the Mark V
behaviour of m2engage in a portable libretro core for Windows, macOS and Linux.
SH2 remains a later implementation phase; Android is deferred.

## First verified block

`src/markv/sh1_hooks.h` implements the SH1 collision-depth block at guest PC
`0x19B93E`. Its reference is the original ARM Thumb handler at file offset
`0x0D57C4` in the pinned m2engage binary:

```text
SHA256 2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f
```

This is **one of the 119 SH1 hook entries**. The portable function is tested
independently and is not yet installed as an interception point in the MAME CPU.
The existing core continues to execute the reconstructed 68000 instructions.

The reconstruction at `0x19B93E` is now `322C`, loading D1 rather than D6. This
preserves the collision-table count in D6. The SH1 patched-ROM SHA1 is now
`718c21dc6e71e6a408bc35ebbe8ea755f3ad69e3`. Load the original `.smp` in the core;
the previous reconstructed ROM is not a supported migration input. The original
ROM on disk is unchanged.

The portable block reproduces the native read order, word alignment, 24-bit
address mapping, partial register writes, signed difference, NZVC and X, guest
resume PC and dispatcher counter. It deliberately applies M2's alignment rule
only inside this HLE block, without changing normal 68000 memory semantics.
The meaning of the counter in the complete scheduler still requires validation.

## Measured reference vectors

`scripts/ghidra/Sh1CollisionOracle.java` runs the **original ARM bytes** in
Ghidra's `PcodeEmulator`. It does not calculate the expected outputs from a
second handwritten version of the algorithm. It checks the binary SHA256 and
locates the handler by file offset, independently of Ghidra's image base.

The oracle stops immediately before the terminal `BX r3`, after all writes and
the stack restoration. It verifies the branch bytes, target and stack pointer.
The dispatcher and its interrupt handling are outside this block-level test.

The fixture `tests/fixtures/sh1_collision_m2.json` records 31 synthetic cases:

- all 25 pairs from depths `0`, `1`, `0x7FFF`, `0x8000` and `0xFFFF`;
- dispatcher counter wraparound;
- odd addresses;
- high address bits and shared-word aliases;
- 32-bit address addition wraparound and a page boundary.

The cases retain nonzero upper halves in data registers. Tests compare D1, D4,
D6, A0, NZVC, X, the next guest PC and the dispatcher counter; they also verify
that unrelated registers survive and that memory reads occur in order. The
fixture contains synthetic state and measured outputs, not ROM or emulator code.

Ghidra is one emulation implementation, not a hardware oracle. The successful
comparison should eventually be cross-checked with an independent ARM execution
engine or original hardware. The earlier Unicorn attempt did not produce a
valid result and is not used by these tests.

## Run the portable tests

The normal suite compiles the small C++ probe with `CXX` (default `c++`) and uses
the committed reference vectors. It needs neither Ghidra nor the private binary:

```sh
python3 -m unittest discover -s tests -v
```

To compare a freshly generated native run as well:

```sh
SH1_ORACLE_JSON=/tmp/sh1-native-run.json \
  python3 -m unittest discover -s tests -p test_sh1_native_hook.py -v
```

The probe requires a C++17 compiler with GCC/Clang-style flags. On a Mac with
mismatched SDK and linker installations, select a compatible installed SDK
using `SDKROOT`; no fixed developer SDK path is embedded in the tests.

## Regenerate the original ARM reference

Ghidra 12.1 with Java 21 was used for the first successful runs. Set
`GHIDRA_HOME`, `JAVA_HOME` and `M2ENGAGE_BIN` to the local installations and binary.
From the repository root, create a new temporary project:

```sh
oracle_dir="$(mktemp -d)"
mkdir -p "$oracle_dir/project" "$oracle_dir/config" "$oracle_dir/cache"
XDG_CONFIG_HOME="$oracle_dir/config" XDG_CACHE_HOME="$oracle_dir/cache" \
  "$GHIDRA_HOME/support/analyzeHeadless" \
  "$oracle_dir/project" SH1Collision \
  -import "$M2ENGAGE_BIN" -noanalysis \
  -scriptPath "$PWD/scripts/ghidra" \
  -postScript Sh1CollisionOracle.java "$oracle_dir/original-arm.json" \
  -log "$oracle_dir/ghidra.log"
SH1_ORACLE_JSON="$oracle_dir/original-arm.json" \
  python3 -m unittest discover -s tests -p test_sh1_native_hook.py -v
```

Review reference differences before replacing the committed fixture. Never
regenerate expected outputs from the portable implementation itself.

## Validate the existing core with SH1

After regenerating the ROM adapter and rebuilding the core, select SH1 alone:

```sh
SH_MDP_GAME=sh1 SH_MDP_ROM_DIR=/path/to/private/roms \
  SH_MDP_CORE=/path/to/shmdp_libretro.dylib \
  ./scripts/run-rom-regressions.sh
```

Use the appropriate `.so`, `.dll` or `.dylib` for the host. The script now finds
`shmdp_libretro` automatically in the default build tree and retains support for
the older `mame_libretro` name. Its default selection remains both games.

The gameplay frontend is a smoke test, not proof of accurate M2 execution. Its
current image checks do not detect every guest exception or rendering problem.
The original 10,000-frame collision probe measured 7,044 out-of-table word reads
with the old instruction and zero with the correction. This proves that local
mechanism; it does not validate every SH1 level or an exact external bug report.

On 5 October 2026, the corrected macOS ARM64 core was rebuilt and exercised for
6,000 scripted frames, then inspected through 8,200 frames. The 31 portable
reference cases passed, including a run with undefined-behaviour sanitization.
The complete configured suite passed 20 tests. Windows and Linux execution,
remaining native hooks, full save-state fidelity, video, audio and complete game
progression are still pending.

## Local interactive test on macOS

The 5 October 2026 live-test package is in
`out/SH1-test-live-2026-10-05-macos-arm64`. Double-click
`TESTER_SH1_MACOS.command` to launch the existing RetroArch installation with the
corrected ARM64 core. The launcher source is kept in `dist/`. It verifies the
original ROM SHA1 and the packaged core SHA256, then uses separate configuration,
save, screenshot and log directories below `session/`. The ROM path is stored
locally in `rom-path.txt`; the ROM itself is not copied into the package.

RetroArch 1.22.1 successfully loaded this package with Vulkan and CoreAudio3. Its
log confirmed the in-memory SH1 patch, and the game was observed in the actual
RetroArch window. The packaged core SHA256 is
`3599aeb01e90be3fbc36a501492fdaf5dce0e598ee0acd21f882bb7a280a9d2b`.
This is the corrected reconstruction core, not an integrated native-HLE build.

Use Enter to start, arrows to move, Z to fire, P to pause, F1 for the menu, F8 for
a screenshot and Escape to quit. These mappings are explicitly configured;
synthetic UI key presses did not provide a reliable interactive-input check, so
physical keyboard/controller testing remains with the tester. The test target
is Stage 1, its boss and the transition into Stage 2. Leave any exception screen
visible and retain the corresponding `session/logs/sh1-*.log`.

## Windows x64 test export

`out/space-harrier-mdp-0.1.2-sh1-test-windows-x86_64.zip` contains the corrected
Windows DLL, its core information, a French guide and `TESTER_SH1_WINDOWS.cmd`.
The launcher asks for RetroArch x64 and the original SH1 ROM, verifies their
architecture/hash as appropriate, and creates a separate session. It removes
the experimental sprite-persistence environment variable and leaves the game's
Deflicker setting alone, matching the Mac test's renderer configuration.

The Windows build uses the same six emulator/ROM-adapter source files as the Mac
test. A separate portability patch removes an unused SDL header dependency from
the libretro input module. Exact source hashes, source patches, the generated ROM
adapter and the cross-compilation command are included in `source-reference/`.
This provenance matters because the local libretro adapter has changes beyond
the public MDP patch alone.

The DLL is PE32+ x86-64, exports all 25 libretro API functions and imports only
Windows system/UCRT libraries; it does not require MinGW runtime DLLs or SDL.
Its SHA256 is
`d99a8118d6afb939f418c772f416aaee12ceae0bc4cfbf0b0b9970ebc151ab57`.
The test package targets Windows 10/11 with RetroArch x64. The UCRT is included in
these operating systems ([Microsoft documentation](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment?view=msvc-170)).

Compilation and binary structure are verified. Neither Windows gameplay nor the
launcher has been executed on a Windows host here. The launcher was reviewed
statically for PowerShell 5.1/cmd.exe and uses a GUI-process output pipeline to
wait for RetroArch ([Microsoft explanation](https://devblogs.microsoft.com/powershell/managing-processes-in-powershell/)).
This remains the reconstructed 68000 core with the SH1 collision fix; full M2
renderer fidelity and integrated native-hook execution are still pending.

## SH1 stage and boss text correction (0.1.3)

The 5 October follow-up fixes the garbled stage and boss introductions. The
renderer applied an SH2 font-bank workaround to every cartridge: high-priority
palette-2 tiles in `6A0..6FF` were redirected to `4A0..4FF`. SH1 intentionally
loads its introduction font into the first bank. Its original ROM descriptor
at `0x2E2F8E` points to font data at `0x2E0D00`, loaded through `0x1EE1AA`.
The affected loader has no M2 hook to reconstruct. The entire 3,072-byte VRAM
bank at the stage 1 and stage 2 introductions matches that ROM font exactly.
The other bank matches a different font at `0x2E1BA0`.

The generated ROM adapter now supplies a compatibility flag only for the exact
original SH2 SHA1 and size. The cartridge clears it on load/unload, and the
machine reapplies it to the VDP after reset. SH1 uses its actual tile indices;
SH2 retains its existing workaround. This flag is independent of the scaler's
layout heuristic. Original ROMs remain the supported inputs; a previously
patched ROM is not recognised as the original SH2 profile.

Validation of the rebuilt macOS ARM64 core:

- 60 attract-mode captures over 3,600 frames: only captures 840 and 900 changed,
  within the introduction rectangle `(104,72)..(216,112)`. The real libretro
  output reads `STAGE 1 / MOOT`; all other captured pixels are unchanged.
- 6,000 scripted frames for each game, compared to the previous core in fresh
  processes. SH2's 5,999 video callbacks and 4,806,980 stereo sample frames are
  identical. SH1's audio is also identical; its font rendering changes as intended.
- Stage 2's `STAGE 2 / GEEZA` font selection is additionally confirmed from a
  standalone VRAM capture reached with the existing assisted boss diagnostic.
  This is data-level evidence, not a full unassisted playthrough of the new core.
- 25 tests run: 24 pass, including five new compiled profile tests and the
  committed original ARM collision vectors. The optional fresh Ghidra oracle
  comparison is skipped. The profile tests stub the hash identity; the actual
  core runs exercise recognition of both original ROMs.

Evidence, before/after captures and exact reports are retained locally in
`out/SH1-text-audit-2026-10-05`. No sprite persistence, Deflicker option or timing
behaviour was changed. Full M2 renderer accuracy remains a separate audit.

Version `0.1.3-sh1-textfix` is packaged for macOS ARM64 and Windows x86_64 as
separate `.7z` archives, each below 10,000,000 bytes. The Windows DLL was rebuilt
from the same eight shared source files, with the separate SDL-header guard.
Its 25 exports and system/UCRT imports were checked; Windows runtime execution
remains untested here. The previous packages remain available.

The public MDP patch also now contains the existing direct-ROM libretro adapter
used by these builds; it was previously missing from that patch. The unchanged
Windows portability guard is retained as `patches/mame0289-libretro-windows.patch`.
Applying both patches to the pinned originals reproduces the Windows sources.
