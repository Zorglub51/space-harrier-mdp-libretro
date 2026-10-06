# Optional SH1 explosion artwork and timing in SH2

This experimental option replaces recognized ordinary-enemy and boss-death
explosions in Space Harrier II with artwork and the shared animation sequence
taken from the user's original Space Harrier ROM. SH2 retains control of object
positions, movement, lifetime, removal and boss progression. It is a gameplay modification, separate from
the core's faithful default emulation. **Original SH2** remains the default.

## Using the option

Place the supported original `jp_jp_space_harrier.smp` beside the SH2 ROM or in
the frontend's system directory. Set **SH2 Explosions**
(`mame_sh2_enemy_explosions`) to **SH1 Artwork and Timing** or **Original SH2**.
Changing this option automatically restarts the complete game on the next
Libretro update. The restart rebuilds the cartridge from the original ROM and
skips native auto-save loading for that restart, so an old auto-save cannot
immediately undo the new mode. Normal close/load auto-save behavior is retained.
The same-directory donor is checked first; a valid system-directory copy can
also be used.

The loader verifies the original SH2 identity and the donor's size and SHA-1.
The supported SH1 donor is 0x3E0000 bytes with SHA-1
`e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`. Missing, unreadable, different or
rejected donor data leaves the original explosions in place and produces a
frontend message. Neither ROM file is modified. No donor artwork, palette bytes
or original guest-code bytes are distributed in the repository.

Enabled-mode Libretro save states use version 2 of the mode marker and cannot
be loaded in original mode; original states cannot be loaded in enabled mode.
Both SH2 modes reserve the same state-buffer capacity, including sixteen bytes
for the marker, so a frontend can allocate once before any option changes.
Original-mode states keep their native payload followed by sixteen zero bytes;
loading also accepts the legacy native payload without that padding.
Version-1 modified states from v0.1.12 are rejected because their guest method
pointers refer to a different implementation. This prevents restored
pointers from referring to resources that are absent in the other mode.
Recognized SH2 content reserves the same state-buffer capacity in both modes,
so an automatic mode change cannot outgrow a frontend's cached buffer. Original
mode stores its native payload followed by 16 zero bytes; active mode uses those
16 bytes as its versioned prefix. Older unpadded original states remain loadable;
nonzero padding, unexpected sizes and mismatched mode/version are rejected.
MAME's separate relative-path disk states and auto-save mechanism use a
`sh2-sh1-explosions-v2` subdirectory only after successful activation, keeping
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
custom reaction callbacks are not intercepted by this ordinary-enemy route. The original SH2 explosion artwork and descriptors remain
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

Boss support uses separate, explicit native death-effect methods. The allocator
at `0x18FC3A` installs particle method `0x137AFC` at two instruction sites. The
adapter replaces those method operands with a visual wrapper. Fifteen audited
tracked hostile-actor death initializers install method `0x137CF0`; their
method operands use a corresponding wrapper. These include boss components
and other counted hostile actors, rather than exclusively whole bosses. The initializers, allocation, sound and damage logic
remain native. The boss controller `0x139396` still creates its particles and
performs its normal completion accounting.

Every update calls the original SH2 handler first: `0x137F0A` for ordinary
effects, `0x137AFC` for boss particles, or `0x137CF0` for tracked deaths. All
native removal paths mark object byte `0x20` as `0xFF`; the wrapper returns
immediately when it sees that mark. It does not restore a descriptor, upload
artwork or relink a freed object. In particular, the tracked method's decrement
of boss counter `0xFF3858` and the separate boss controller remain intact.
New boss particles acquire the replacement on their first native update.

The replacement uses eleven poses, each with four source sizes: 16×16, 48×40,
80×64 and 112×88. These are distance levels, not four extra animation frames.
Only artwork, palette and composition records are copied from the donor.
Generated guest code implements the verified shared animation rule; no SH1
motion, clipping, lifetime or free-list code is transplanted. SH2's projection
and descriptor-driven size selection are retained. See
[the timing reference](SH2_EXPLOSION_TIMING.md) for the verified donor clock,
geometry, palette cycle and the explicitly identified host adaptations.

An aerial explosion can still fall toward the ground: native SH2 sets vertical
velocity to `-(Y >> 2)`, bringing the observed aerial effect to ground level in
four game updates. Keeping native SH2 movement removes the earlier transplant's
small Y overshoot and one-update depth lag; it does not invent a floating effect.

All live modified explosions share the same texture cache and animation phase,
as in the donor. A new explosion resets that phase; the next handler update
loads pose one. Later poses advance when the game clock divided by four changes,
and pose eleven is held while the native SH2 object remains alive. There is
no invented fixed eleven-times-eight-video-frame lifetime. With another modified
effect already active, its shared pixels are retained until that update. Without
another active effect, the ordinary-enemy constructor preloads pose one so its
first display has defined graphics; its handler initializes phase at its next
update. Pending boss wrappers already animate during initialization, so they
perform a single upload in that update rather than duplicating a cold preload.
Boss particles retain their shorter native lifetime and need not display all
eleven poses. Rapid particle creation also restarts the shared phase repeatedly,
so an active burst can stay on the early images. Native age limits and the
completion-counter rule remain unchanged; additional guest execution can still
extend wall-clock time, as measured below.

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
| `0x380100`–`0x3808FF` | Constructor, three native-first wrappers, trampoline and palette adapter |
| `0x380900` | Recognized actor-method table |
| `0x380A00`–`0x380EFF` | Visual initialization, pending particle/tracked wrappers and LOD selector |
| `0x381000` | Generated shared animation and image-upload routine |
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

Before ordinary-enemy activation and after each native handler, the adapter checks the host's
tile-loading cursor at `0xFF3842`. If it has advanced beyond tile `0x6F4`, the
adapter uses the original SH2 effect instead of writing into potentially occupied
cache space. Returning an active effect to its native handler does not restart
its age, delay or movement; the original descriptor's size selection is restored.
The activation and fallback counters are retained in emulated RAM
for diagnostic traces. This is a bounded guard, not a proof that every stage's
asset lifetime has been exhaustively characterized.

## Executed validation and remaining limits

Current checks are recorded in
[SH2_EXPLOSION_V013_VALIDATION.json](SH2_EXPLOSION_V013_VALIDATION.json).
The native-first update matched X, Y, vertical velocity, depth and projected
coordinates for 34 samples across two ordinary explosions. A separate diagnostic
confirmed all eleven shared poses and all 44 donor payloads after the rewrite.
The stage-four run again observed seven modified enemy destructions with zero
cache fallbacks. Frontend tests cover automatic mode changes, state isolation
and missing-donor behavior; the manifest identifies the tested core hashes.

The boss check used the final candidate in both modes and deliberately installed
the native death controller in a valid live object during stage one. Its position
and speed were controlled, and only that controller's random-number calls used
fixed inputs. This is a controlled death-sequence test, not a naturally defeated
boss. Both modes created 21 particles; all 21 enabled particles used SH1 artwork,
with zero cache fallbacks. Each reached native age 30 and was removed. The
controller reached age 41, decremented the boss counter from one to zero once,
and the counter remained zero for the rest of the run. Matching random inputs
produced identical particle world coordinates, and captures visibly showed the
different artwork.

The extra guest work delayed the completion-counter change by 22 video frames
in this fixture (frame 3149 in original mode, 3171 with SH1 artwork). The last
particle disappeared at frames 3208 and 3237 respectively. The shared burst
reached pose eight before the last native particle expired. These measurements
preserve the distinction between unchanged lifetime rules and changed execution
cost. Ordinary boss scatter is not expected to match across separate modes:
the game's random routine reads the VDP beam counter, which can change when
additional instructions run. Every boss battle and custom effect path has not
been exercised.

The earlier checks are recorded in
[SH2_EXPLOSION_VALIDATION.json](SH2_EXPLOSION_VALIDATION.json). The following
stage-coverage and clock-overhead measurements were established for v0.1.12;
they do not by themselves validate the later boss wrappers. Its final
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
disabled by default and applied through a complete game restart.
