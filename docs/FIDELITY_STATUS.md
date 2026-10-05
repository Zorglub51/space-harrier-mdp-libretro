# Fidelity status — 0.1.9

The target is the original M2 emulator output for SH1 and SH2, including its
pixel alternation and flicker. An attractive image or a plausible reconstruction
does not establish fidelity. Changes should be supported by native execution,
traces or an explicitly documented integration requirement.

The reference ELF SHA-256 is
`2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f`.
The repository contains synthetic oracle fixtures and reproduction tools, but
no original executable, ROM, captured game memory or game pixels.

## Measured contracts

| Area | Evidence | Boundary |
|---|---|---|
| SH1 collision block | 31 original ARM executions | One hook; other hooks are not thereby validated |
| SH2 line-phase reset | 33 original ARM executions | Restores the omitted phase reset |
| SH2 pre-boss lightning tilemap | 76 original ARM cases and 19,200 game writes | Restores the omitted source read; see [the lightning reference](SH2_LIGHTNING_REFERENCE.md) |
| Direct CRAM addressing | Original handler and bus traces | Addressing is established; scheduling is separate |
| Direct low VRAM writes | Native decoder and game write trace | Ranking-font data reaches VRAM without a font remap |
| Direct video registers | 68 original ARM cases | All 64 registers; byte enables tested as MAME integration |
| Transformed planes | 30 original ARM cases | Table selection, coordinates, wrapping, tile attributes |
| Sprite geometry and reduction | Original ARM helper fixtures | Zoom, height, row, table selection and left-cell clipping |
| Sprite selection and full sprite layer | 76 original ARM cases | Native budgets, cycles, table addressing, stop rules, overlap, banks and attribute carries |
| Shadow composition | 208 original ARM cases | Priority and intensity operators, including upper palette |
| Colour output | 4,115 original ARM cases | Native RGB4440 colormap; all CRAM words tested in C++ |
| Combined indexed rendering | 143,360 equal pixels in 0.1.8 | Two complete captured SH2 frames; coverage below |

The combined renderer comparison executes original M2 instructions through
indexed composition. Version 0.1.7 compared 224 lines of one SH2 stage-4 frame, and 11
lines each of an SH2 stage-1 scene, an SH2 stage-3 scene and an SH1 scene:
71,680 + 3 × 3,520 pixels, with zero differences. Each input buffer was checked
against the captured state. Eight stage-4 lines with an upper-VRAM mutation were
replayed on both sides of that mutation; their native output was identical.
See [the frame oracle contract](MDP_FRAME_ORACLE.md) for capture assumptions.

Version 0.1.8 compares two complete SH2 frames: the stage-4 reference and a
sprite-heavy scene near the first boss. All 143,360 indexed pixels match M2.
The latter frame exposes 30 sprite-pixel differences in version 0.1.7, now fixed.
The [sprite list reference](MDP_SPRITE_LIST.md) and its
[validation manifest](MDP_SPRITE_LIST_VALIDATION.json)
record this coverage and the treatment of palette input changes.

The ARM oracle stops before the renderer's NEON palette conversion. Colour is
validated separately: M2 packs normal channels as twice the three-bit CRAM
component and shadow channels as the component itself; its `229E08` colormap
callback replicates each four-bit channel to eight bits. Hence normal RGB is
`34*c`, shadow RGB is `17*c`. The constructor/frame path binds this colormap to
MDP, and the RGBA8 format converter preserves those values. GPU surface formats
and shaders remain a separate presentation boundary.

The old compositor produced 722 differences on the stage-4 frame, all in the
player's shadow. Additional SH1 lines exposed three left-edge pixels. Both
differences are fixed. The port's empirical two-frame background average and
optional sprite persistence are removed; final frontend pixels now agree with
the raw scanline output on the captured lines.

## Reliability checks

Version 0.1.9 changes only one SH2 reconstruction instruction. Its lightning
transitions are checked against 19,200 expected source-tile writes. Separate SH1
and SH2 control sequences retain identical video/audio over 21,000 frames.

The 0.1.8 validation replays six deterministic SH1/SH2 scenarios over 39,020
frames. Their PCM streams match 0.1.7 exactly. This checks execution stability;
it is not a comparison of audio or CPU timing with the M2 binary.

With default audio settings, saving and restoring SH1 and SH2 reproduces all
180 subsequent frames and audio samples in each test. Since 0.1.7, the state includes
the upper 64 KiB of MDP graphics memory and the audio filter's delay samples.
An earlier build fails this same audio comparison, providing a regression
check for the history fix. States from versions before 0.1.7 are incompatible.

Run the private-ROM test with a locally built core:

```sh
python3 tests/libretro_state_regression.py \
  --core /path/to/shmdp_libretro.so --rom /path/to/original.smp \
  --frames 180 --output /tmp/state-result.json
```

The script uses isolated configuration directories and emits hashes, not game
content. Its automatic input sequence reaches SH2 stage 4 or SH1 gameplay.

## Remaining discrepancies and unproved assumptions

| Area | Current concern | Required next comparison |
|---|---|---|
| Palette timing | The renderer's counter now dates the queue, correcting the 38-line origin difference; direct and ordinary writes still take different paths | Mixed-write ordering, readback and transition-frame traces |
| CPU and video timing | MAME CPU clocks, DMA and interrupt delays remain in use | Native scheduler traces and full deterministic sequences |
| Extended VSRAM | Direct MDP access and native leading-word layout are not fully integrated | Original access-handler cases and game traces |
| Reconstructed game hooks | Most reconstructed instructions have not received isolated original-ARM comparisons | Prioritize hooks reached in remaining SH2 glitches, then broaden coverage |
| Compatibility guards | Divide guards, SH1 tree insertion, shot counter and boss-exit handling include empirical choices | Original hook/game-state execution for each affected case |
| Reset and reload | Save/load is tested; wider reset/reload sequences remain | Default-state and repeated-content tests on all platforms |
| Host presentation | Actual M2 GPU texture format and active shaders are not established | Trace texture upload and presentation configuration |
| Scene/platform coverage | Only the stated scenes have native pixel comparisons; interactive testing is mainly on Mac | More stages, bosses, menus and Windows/Linux sessions |

The [raster timing reference](MDP_RASTER_TIMING.md) establishes the native
render-before-CPU ordering and documents the measured counter correction.
The remaining items prevent a whole-core "100% pixel perfect" claim. They are explicit
follow-up work, rather than reasons to alter coordinates or suppress flicker by
eye. A complete-frame match at identical video state validates the renderer on
that state; it does not prove the emulator reaches that state at the same time.
