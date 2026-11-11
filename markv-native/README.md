# Mark V

Independent C++20 implementation for the Japanese Space Harrier and Space Harrier II
Mark V cartridges. The emulator contains its own instruction decoders, memory bus,
interrupt scheduler, DMA and scanline renderer. It runs the original `.smp` files
using in-memory instruction fetch profiles for the two known revisions.

`src/rom_profile.cpp` records the original and recovered guest instruction words
from the project's [Mark V hook audit](../docs/MDP_HOOK_AUDIT.md) and previous
research. Cartridge data reads see the original words. Both game profiles skip
their object-position average when there are zero active objects. This avoids
the division by zero during the stage 15 attract demo in Space Harrier and the
transition into gameplay in Space Harrier II. The interpreter still raises
the 68000 divide-by-zero exception for ordinary guest instructions. The
compatibility behavior needs comparison with the original M2 runtime.

The renderer replays the existing SHGP captures pixel for pixel, including raw
sprite samples. This checks the renderer for captured input states. The full
machine has reached the first stage with scripted controller input in both
original ROMs.
CPU coverage and timing are still partial. The sound driver runs on the Z80
and feeds a stereo mixer with YM2612 FM, DAC samples and PSG tone and noise.
The FM operator routing, phase, panning and envelopes are derived from the
[Yamaha OPN2C application manual](https://www.aidanlawrence.com/wp-content/uploads/2018/05/YM3438_APL.pdf).
The operator-to-operator phase input uses the wiring documented in
[YM2612 hardware tests](https://gendev.spritesmind.net/forum/viewtopic.php?t=518).
The PSG register interface follows the
[TI SN76489AN data sheet](https://map.grauw.nl/resources/sound/texas_instruments_sn76489an.pdf)
with Sega's 16-bit noise generator. FM envelope rates, detune, sample timing
and analogue output are approximations. The traced game sessions used the
normal FM mode with LFO and SSG disabled. Those optional modes and channel 3
special modes remain to be implemented, along with save states.

## Core options

NextUI and RetroArch expose separate **FM Level**, **PCM Level** and **PSG Level**
controls. Each accepts 0%, 25%, 50%, 75% or 100%, with 100% as the default.
These levels apply before the stereo output filter and update during gameplay.

**Widescreen** renders at 426 × 224 with a 16:9 presentation. The scenery is
sampled 53 pixels farther to each side. The hardware window stays inside the
original field, and the game keeps its own movement and object lifetimes.
Widescreen on its own uses the original sprite quotas.

**Mark VI** removes the native sprite and tile-column quotas and reconstructs
the two games' sprite pieces at the original object constructor, ahead of the
game's 40/80-entry partitioning. The matching completed sprite-table upload
selects which list is shown. The renderer suppresses the documented depth
thinning, SH2 stage 7's alternating body mask, and the traced Harrier blink
poses. A real pose change, despawn or spatial hide is still a game decision.
See the [SH1 visibility audit](../docs/SH1_MARK_VI_AUDIT.md) and the
[SH2 visibility audit](../docs/SH2_MARK_VI.md#stage-7-bosss-upstream-visibility-budget-0121).

Both video options default to off. They can be combined and changed while the
game runs on a frontend that accepts geometry updates.

Desktop builds also expose **120 Hz** in RetroArch's **Quick Menu > Core Options**.
This presents at 119.845 Hz by inserting a frame with interpolated sprite
positions and zoom between native frames. It works with either aspect ratio
and with Mark VI off or on. Background and sprite artwork changes use their
native cadence. The CPU, input sampling and audio generation still run once
per native frame. The native and intermediate images share the same
background rendering pass. Set the display and RetroArch's output refresh
rate to 120 Hz to see every presentation. If the frontend reports an output
rate more than 1 Hz below the doubled cadence, the core uses native timing
and shows a message. After changing the output refresh rate,
reload the game or toggle the option off and back on.

## Build and verify

```sh
make -j4 all test
make test-attract ROM="/path/to/Space Harrier.smp"
build/markv-run --exercise "/path/to/game.smp" 4200 output.ppm
build/markv-run --exercise --mark-vi --widescreen "/path/to/game.smp" 4200 wide.ppm
build/markv-replay --verify /path/to/captures/raster-*.bin
build/markv-replay --bench 32 /path/to/captures/raster-*.bin
```

The machine benchmark measures video and sound synthesis inside `Machine::frame()`.
It reports the emitted stereo sample count and peak amplitude after timing each frame.
Frontend display, resampling and pacing are measured separately on the TrimUI.

For macOS, build a universal core for Apple Silicon and Intel. On desktop
Linux, the default target builds a `.so` for the compiler's architecture.
For Windows x86-64, use a MinGW C++20 compiler.

```sh
make libretro BUILD=build/macos SHARED_SUFFIX=dylib SHARED_FLAGS=-dynamiclib \
  CXX='clang++ -arch arm64 -arch x86_64 -mmacosx-version-min=11.0'
make libretro BUILD=build/linux
make libretro BUILD=build/windows SHARED_SUFFIX=dll \
  CXX=x86_64-w64-mingw32-g++ LDFLAGS='-static -s'
```

Open the resulting library with **Load Core** in RetroArch and select your
original `.smp` file with **Load Content**. For Linux ARM64 on the TrimUI,
build with Zig targeting Cortex-A53 and glibc 2.28. The NextUI build omits
the desktop refresh option.

```sh
make -j4 all libretro BUILD=build/arm64 DESKTOP_120=0 LDFLAGS=-Wl,-s \
  CXX='zig c++ -target aarch64-linux.4.9-gnu.2.28 -mcpu=cortex_a53 -Wno-nullability-completeness'
sh nextui/package.sh build/arm64 dist ../dist/nextui/licenses
```

Pass a fourth argument containing `SH1/` and `SH2/` recordings to build the
private comparison archive. See the [NextUI test instructions](nextui/TEST.md).
