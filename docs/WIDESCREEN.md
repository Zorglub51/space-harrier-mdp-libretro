# Extended 16:9 presentation (0.1.19)

`mame_mdp_aspect` is independent of `mame_sh2_rendering`, native Deflicker and
SH1 explosion selection. Values are `original` (default) and `widescreen`.
The driver enables it only for authenticated SH1/SH2 cartridges after validating
all instruction sites against their restored ROM. No disk ROM is modified.

## Raster and physical aspect

Native 320x224 output is presented as 4:3, so preserving the physical pixel aspect
requires `320 × (16/9) / (4/3) = 426⅔` source pixels. The even integer 426 permits 53 whole
pixels per side; the advertised 16:9 aspect gives less than 0.16% pixel-aspect
rounding. Choosing a square-pixel width or stretching 320 would change proportions.

The native 320-pixel path is unchanged. A transient 106-pixel cache extrapolates
transformed planes to logical X=-53..-1 and 320..372 using the same signed affine
steps, texture wrap/clamp, tile samples and compositor. Standard planes extend
with their native scroll/priority rules. The hardware window remains central.
RGB conversion copies the unchanged center 53 pixels to the right, then places
the two side bands. Both 120 Hz phases independently build their side cache.
The VDP total width stays 480: extending visibility does not change screen timing.

Native sprite selection retains its existing budgets; only the raster bounds
expand. Mark VI widens its host constructor cull and keeps its unbounded list.
Its native guest constructor does not need extra side pieces, so those guest
cull substitutions apply only to SH1 or original SH2 rendering.

## Visibility and object lifetime

`src/markv/sh_widescreen_patch.h` records verified instruction pairs rather than
replacing every constant 320 in the games. Thirty-six immediate sites per game
extend piece clipping. Separate verified offscreen-removal comparisons preserve
the native 36-pixel margin around the wider field (38 pairs in SH1, 8 in SH2).
Collision/aiming arithmetic and enemy behavior/turning thresholds stay intact.

A six-byte unsigned screen-space projectile X guard is replaced by an absolute
jump to a 34-byte comparison trampoline at 3FF000. It accepts unsigned(X+53)<=426,
then returns to the native Y comparison or native object removal. D0, D2, A1, SP
and X are preserved; NZVC reflects the new comparison. That cartridge-bus range
is beyond both original images and the optional SH1-art injection. The jump is
conditional on the option; stub words remain mapped even in 4:3 so an in-flight
or restored PC can finish safely. Full surrounding opcode validation precedes
installation. Switching off restores original instruction reads immediately.

Wider offscreen lifetimes can retain actors/projectiles in their pools longer,
and some native cleanup paths update counters used for phase completion. Thus
wide gameplay need not have identical RAM/audio/timing to a 4:3 run. Movement
limits, collision formulas, artwork and animation clocks are unchanged. This is
an optional adaptation, not claimed as pixel-perfect M2 output. Original-mode
quotas can omit more central pieces when extra side pieces occupy its list.

## Frontend and saved output

Format preferences apply only after a pending 120 Hz half has been delivered.
The frontend derives display aspect from the actual source width, separately
from arbitrary software output sizes such as 640x480. It reports fully initialized
geometry before video delivery. A saved pending half includes its source width,
so restoring across format preferences retains the correct aspect for that
image. This field makes earlier binary state layouts incompatible. All current
options share one layout; keep the same preferences for identical replay.

## Validation

`WIDESCREEN_VALIDATION.json` records hashes and results without private game data.
Synthetic public tests exercise production raster/frontend functions, instruction
validation, signed bounds, register-preserving trampoline structure and format
switches. Private MAME execution checks the actual 68000 instructions for both
games, including negative coordinates and flags. Integration compares 4:3 output
to 0.1.18 and wide 120 Hz to wide native-refresh execution; it also covers both
games, stages 1/3/4/5, donor artwork, Deflicker, threaded rendering, alternate
resolution and state replay. Captures show continued ground and side sprites;
static title artwork remains centered. Whole-game visual coverage is not claimed.
