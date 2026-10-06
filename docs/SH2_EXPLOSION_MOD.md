# Optional SH1 enemy explosions in SH2

This experimental option replaces the selected ordinary-enemy explosions in
Space Harrier II with artwork and the shared animation sequence taken from the
user's original Space Harrier ROM. It is a gameplay modification, separate from
the core's faithful default emulation. **Original SH2** remains the default.

## Using the option

Place the supported original `jp_jp_space_harrier.smp` beside the SH2 ROM or in
the frontend's system directory. Set the SH2 enemy-explosion core option
(`mame_sh2_enemy_explosions`) to **SH1 Artwork and Timing**, then close and reload
the content. A frontend reset (`retro_reset`) does not reload the ROM or change
the selected mode. The same-directory file is checked first; a valid
system-directory copy can also be used.

The loader verifies the original SH2 identity and the donor's size and SHA-1.
The supported SH1 donor is 0x3E0000 bytes with SHA-1
`e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`. Missing, unreadable, different or
rejected donor data leaves the original explosions in place and produces a
frontend message. Neither ROM file is modified. No donor artwork, palette bytes
or original guest-code bytes are distributed in the repository.

Changes take effect when the content is closed and reloaded. Enabled-mode
Libretro save states have a versioned marker and cannot be loaded in original
mode; original states cannot be loaded in enabled mode. This prevents restored
pointers from referring to resources that are absent in the other mode.
MAME's separate relative-path disk states and auto-save mechanism use a
`sh2-sh1-explosions-v1` subdirectory only after successful activation, keeping
those states separate as well. Missing or invalid donor data retains the
original state namespace, matching the mode actually loaded. The folder is
chosen for each save/load operation without changing persistent MAME options.
Manually supplied absolute MAME state paths are not redirected; this exception
does not affect the Libretro state marker check.

## Scope of the guest patch

The adapter intercepts SH2's shared constructor at `0x139B84`. Both of the host's
generic collision loops can hit enemies as well as scenery, so the caller alone
is insufficient. The replacement requires all three conditions:

- The return address is one of `0x1719DC`, `0x171E7A`, `0x171F36` or `0x172132`.
- The object's current reaction byte at offset `0x23` is zero.
- Its original method belongs to one of the 50 audited ordinary-actor methods
  listed below.

All other calls continue through the original constructor. In particular, the
shared scenery methods, player-collision caller `0x1798EA`, unknown methods and
custom reaction callbacks, including the boss paths examined during the audit,
are not replaced. The original SH2 explosion artwork and descriptors remain
intact for those uses and for fallback.

The audited level-spawn code contains 72 direct calls to the actor factory at
`0x13D6B4`, with immediate method and descriptor operands. Of these, 51 sites
cover 50 distinct methods whose final initialization sets reaction zero. Other
sites use nonzero or custom reactions. Two further references to the factory
load a function pointer into A6 for special nonzero/custom-reaction paths;
these are excluded. The scenery factory is `0x13D5C4`, with its separately
initialized scrolling-object methods such as `0x0F14A2` and `0x0F15E8`.
The adapter verifies the 51 recognized spawn signatures and their reaction
initializers before installing the method table. It does not infer entity type
from palette number, a visual resemblance or one unproven flag bit.

| Initial descriptor | Recognized method addresses |
| --- | --- |
| `0x000C56` | `0x0E7138`, `0x0E8E26`, `0x0EB42A`, `0x0EDA2E`, `0x0F1748`, `0x0F3D8E`, `0x0F63CE`, `0x0F8AC4`, `0x1029FA`, `0x1467A4`, `0x149FD8`, `0x14BF66`, `0x14DEF4` |
| `0x000CC4` | `0x13DDFC`, `0x185284` |
| `0x000DB6` | `0x11D1BC`, `0x14393A` |
| `0x000DF8` | `0x0FB2D4`, `0x0FDB56`, `0x1002A8`, `0x1174D8`, `0x14FE84`, `0x155B68` |
| `0x000E3A` | `0x0B0D18`, `0x0B2CBE`, `0x0B4C64`, `0x0B6FF4` |
| `0x000EBE` | `0x0B9384`, `0x0BBD62`, `0x0BE740`, `0x0C06DA`, `0x12F148`, `0x13183A`, `0x133F2C`, `0x135BE6` |
| `0x000F2C` | `0x114FD4`, `0x116256` |
| `0x0013FC` | `0x0AF9CC`, `0x0D4D44`, `0x0D6BAA`, `0x0D85C4`, `0x0D9FDE`, `0x0DAE0E`, `0x0DBC3E`, `0x0DCB7E`, `0x0DDECC`, `0x0DFA6A`, `0x0E1608`, `0x0E346C`, `0x0E52D0` |

The initial descriptor can subsequently change during the actor's script, which
is why runtime selection uses its method. The `0x13FC` family is the cannon
robot; `0x14393A` with initial descriptor `0xDB6` is an armed robot. Both were
confirmed from their actual ROM geometry and runtime objects. The static spawn
map covers these registered families across the level scripts; dynamically
created objects outside this map remain original rather than being guessed.

The replacement uses eleven poses, each with four source sizes: 16×16, 48×40,
80×64 and 112×88. These are distance levels, not four extra animation frames.
The original SH1 handler is copied from the authenticated donor and its known
addresses are relocated to the host's corresponding state and routines. The
host projection tables and immediate constructor-time size selection remain
SH2's. See [the timing reference](SH2_EXPLOSION_TIMING.md) for the verified donor
clock, geometry, palette cycle and the explicitly identified host adaptations.

All live modified explosions share the same texture cache and animation phase,
as in the donor. A new explosion resets that phase; the next handler update
loads pose one. Later poses advance when the game clock divided by four changes,
and pose eleven is held until motion or clipping removes the object. There is
no invented fixed eleven-times-eight-video-frame lifetime. With another modified
effect already active, its shared pixels are retained until that update. Without
another active effect, pose one is preloaded so the first display has defined
graphics; the handler still initializes its phase at its own next update.

Palette color 8 has its own six-step cycle, independent of new explosions.
All eleven verified increments of the SH2 game clock are routed through a shared
adapter that performs the original increment, updates that cycle when appropriate,
and preserves the original condition codes. This follows the donor formula and
cadence, anchored to SH2's clock; it does not claim an absolute presentation phase
shared between two separate games.

## ROM and runtime storage

The loader applies the adapter transactionally to the compatibility-patched,
big-endian SH2 image after padding it to 4 MiB, before the normal byte swap.
Validation failure discards the temporary result. The standalone builder checks
instruction signatures, all original descriptor slot IDs, piece dimensions,
tile counts and donor pointer bounds before constructing the candidate.

| Area | Purpose |
| --- | --- |
| `0x380100`–`0x3808FF` | Constructor, update guard, first upload and palette adapters |
| `0x380900` | Recognized actor-method table |
| `0x381000` | Relocated SH1 handler copied from the local donor |
| `0x382000` | Eleven groups of four descriptors |
| `0x382400` | Relocated piece geometry |
| `0x384000`–`0x39B07F` | 44 image payloads, totaling 94,336 bytes |
| `0x39C000` | Palette copied from the local donor |
| RAM `0xFE0000`–`0xFE0015` | Cache base, phase, clock quotient, palette state and counters |
| RAM `0xFE0100` | Relocated tile-slot table, including four added slots |
| VRAM `0xD1DE80`–`0xD1FFFF` | Shared 8,576-byte image cache |
| CRAM entries 112–127 | Dedicated extended palette bank 7 |

All 190 audited references to the original tile-slot table are redirected, and
the four additional slots are `0x180`–`0x183`. The original 384 descriptor records
and 1,534 pieces do not use the extended sprite-palette bit added by the adapter.
That scan establishes separation from these assets, not from every conceivable
custom SAT-writing routine.

Before creation and each subsequent handler call, the adapter checks the host's
tile-loading cursor at `0xFF3842`. If it has advanced beyond tile `0x6F4`, the
adapter uses the original SH2 effect instead of writing into potentially occupied
cache space. The activation and fallback counters are retained in emulated RAM
for diagnostic traces. This is a bounded guard, not a proof that every stage's
asset lifetime has been exhaustively characterized.

## Executed validation and remaining limits

The machine-readable checks are recorded in
[SH2_EXPLOSION_VALIDATION.json](SH2_EXPLOSION_VALIDATION.json). The final
9,000-step stage-one run used ordinary scripted movement and firing, with lives
held at nine solely to continue the diagnostic through the first boss approach.
Enemy positions, animation state and destruction logic were not forced in that
run. It observed four modified enemy destructions from methods `0x0F63CE`
(twice), `0x0F8AC4` and `0x1467A4`, with zero cache fallbacks. Other observed
constructor calls from `0x1798EA`, `0x1719DC` and `0x171E7A` retained the original
effect and did not increment the modification's activation count. The final
method-based classifier preserved those observed exclusions. The first boss
approach was visually inspected; boss destruction was not tested by that run.

A second 9,000-step run selected stage four and used movement in four directions
while firing, with the same diagnostic life counter. All seven observed enemy
constructor calls activated the replacement: `0x0AF9CC`, `0x0D6BAA`,
`0x0D4D44` (three times), `0x14393A` and `0x0DAE0E`. There were zero cache
fallbacks. This exercised first-loop callers as well as the second loop,
including the previously missed cannon-robot family. That final trajectory
did not destroy scenery; the scenery exclusions above come from the separate
final stage-one run.

A separate forced-position diagnostic exercised all eleven poses and coexistence
of two effects. Every one of the 44 image payloads matched the donor bytes in
VRAM, and the second constructor preserved the existing cache until the next
handler update. The timing reference separates this forced-position evidence
from ordinary-play coverage.

The enabled guest code has a measurable CPU cost outside the explosion itself.
In a controlled 2,600-step run, the palette-clock adapter changed 19 introductory
images before the first enemy explosion: even-numbered frames 2508–2544 differed
by 3–96 pixels each. Redirecting only its CRAM write to an unused RAM word,
while retaining the instructions, preserved the enabled run's complete video
and audio hashes. Restoring the eleven original increments instead recovered
the original-mode video and audio hashes exactly. Thus this difference comes
from the additional guest execution time, not a collision with the extended
palette bank. The enabled audio stream also differs at the sample level; an
audibility or perceptual threshold is not claimed.

Original mode remains unchanged. Enabled mode is an experimental first trial:
the source artwork, transferred bytes and shared animation rules are verified,
but identical host raster timing, every stage, every boss, every custom sprite
path and complete-game behavior are not claimed. The larger graphics uploads
also consume guest execution time. These limits are why the option is explicit,
restart-only and disabled by default.
