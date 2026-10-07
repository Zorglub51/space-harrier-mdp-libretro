# Mark VI: unbounded SH2 sprite presentation

`mame_sh2_rendering` offers `original` (default) and `mark_vi` (experimental).
Only the authenticated SH2 cartridge enables the enhancement. The original
M2-compatible pixel path remains unchanged. No additional ROM patch, guest
RAM write, CPU overclock or extra game update is needed for Mark VI.

## Construction before quotas

The translation in `src/markv/sh2_markvi.h` follows the restored SH2 constructor
at `13B000..13D21E`. It traverses the active object chain at `FF38F2`, reads the
22-byte pose descriptors and 12-byte piece records, and retains the native
signed arithmetic, horizontal visibility tests, tile increments, palette/bank
selection, four flip combinations, mirrored double assemblies and shadow pass.
The allocation-table address is read from the live authenticated ROM operand,
so the optional SH1 explosion cache relocation remains supported.

The native emitter partitions its output into 40/80-entry buffers. Its SAT
links and transform indices are seven bits wide. Mark VI constructs a host
`std::vector` instead: each record has its own coordinates, tile attributes and
zoom value. There is no 128/256/512-entry selection array or arbitrary sprite
budget. Invalid/cyclic object chains are rejected, rather than followed forever.
The game's object pool, allocation, lifetime and deliberate invisibility flags
remain gameplay decisions. The enhancement does not create additional enemies.

Both the body and shadow passes preserve their object/piece traversal order.
Pixel sampling uses the verified M2 cell-scaling algorithm, palettes and priority
bits. Mark VI draws every intersecting entry in reverse traversal order so the
first piece wins an overlap. It does not retain previous-frame pixels.

## Timing and buffer lifetime

Read-only observers capture 128 KiB of work RAM at native constructor entry,
separately for the two producer banks. A completion observer records the native
SAT geometry for that bank. The host list is promoted only on the corresponding
complete SAT DMA upload. Link-byte repairs are ignored in the comparison;
geometry changes caused by a bank clear/replacement invalidate the snapshot.
Direct VRAM writes/fills also invalidate a displayed host list. This prevents
old title sprites from appearing with newly loaded stage artwork.

Three fixed RAM snapshots and their lifecycle metadata are saved. The variable
host vector is rebuilt after state load. This changes the MAME state layout:
pre-0.1.16 states are incompatible. Both rendering modes within 0.1.16 share the
new format, and the current core preference controls the next rendered frame.

This changes presentation, not simulation. Extra construction/drawing runs on
the host, without consuming additional emulated 68000 cycles. Native Deflicker
continues to control the original guest lists; Mark VI obtains pieces before
those lists lose entries. Original speed, collisions, audio and animation
cadence are retained. Interpolation and new animation poses are not included.

## Evidence and limits

[SH2_MARK_VI_VALIDATION.json](SH2_MARK_VI_VALIDATION.json) records the tested core
hash and integration results. Private game data and images are not distributed.

- 5,182 native emitted records from stage 1 and 3,196 from stage 4 are found
  identically in the compiled host constructor's output.
- Controlled native-constructor runs vary all eight assembly flags and scaled/
  unscaled paths: another 7,364 records match, including mirrored assemblies.
  These modified diagnostic scenes reached 171 host entries.
- Synthetic public tests exercise 600 pieces, 200 independent object transforms,
  signed rounding, mirroring/palettes, relocated tile caches, cyclic/dead/hidden
  objects, zero-height sprites, overlap order and empty frames.
- Production-method tests check producer completion, matching uploads, relinking,
  external clears and unknown sources. Renderer/lifecycle probes pass ASan/UBSan.
- 7,000-step stage 1/3/4 runs change 1,668/1,058/1,472 video frames respectively.
  Full PCM streams and sampled 128 KiB work RAM plus eighteen 68000 registers
  match the corresponding original-rendering runs. Samples occur every 120
  video frames; this is not an instruction-by-instruction proof.
- Additional runs cover ON1/ON2, SH1 explosion artwork, state replay and threaded
  mode switching. Default SH2 and SH1 with Mark VI selected retain their measured
  baseline video/audio/game state. A title-transition capture verifies that the
  stale-logo regression was removed.

These are targeted sequences and controlled constructor comparisons, not full
playthroughs of every stage/boss or an independent original-ARM oracle for the
entire constructor. Capacity limits have been removed from this host path;
intentional blinking remains. No universal real-time performance or 120 FPS
claim is made. The original M2 renderer still passes its 76-case native fixture.
