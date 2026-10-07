# Optional SH1 explosion artwork and timing in SH2

This experimental option replaces all objects using SH2's explosion effects in Space Harrier II with artwork and the shared animation sequence
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

Enabled-mode Libretro save states use version 3 of the mode marker and cannot
be loaded in original mode; original states cannot be loaded in enabled mode.
Both SH2 modes reserve the same state-buffer capacity, including sixteen bytes
for the marker, so a frontend can allocate once before any option changes.
Original-mode states keep their native payload followed by sixteen zero bytes;
loading also accepts the legacy native payload without that padding.
Modified states from v0.1.12 and v0.1.13 are rejected because their injected
methods and graphics allocation differ. Nonzero padding, unexpected sizes and
mismatched mode/version are rejected before MAME receives the payload.
MAME's separate relative-path disk states and auto-save mechanism use a
`sh2-sh1-explosions-v3` subdirectory only after successful activation, keeping
those states separate as well. Missing or invalid donor data retains the
original state namespace, matching the mode actually loaded. The folder is
chosen for each save/load operation without changing persistent MAME options.
Manually supplied absolute MAME state paths are not redirected; this exception
does not affect the Libretro state marker check.

## Scope of the guest patch

The shared explosion constructor at `0x139B84` is intercepted without filtering
its caller, the previous actor method or reaction byte. Enemies, scenery,
player-collision effects and dynamically created objects therefore use the same
replacement whenever the original game creates an explosion.

Custom death callbacks can bypass that constructor. Every direct assignment of
the three native explosion methods is covered as well:

| Native update | Initializer coverage |
| --- | --- |
| `0x137F0A` | Shared constructor plus seven direct assignments at `0x114D94`, `0x15840E`, `0x158738`, `0x158A62`, `0x15E4C4`, `0x15E6E2`, `0x16EC0C` |
| `0x137AFC` | Two particle assignments at `0x18FC88`, `0x18FE36` |
| `0x137CF0` | Fifteen tracked-death assignments, including boss components |

The private-ROM regression test independently scans all aligned references to
these native methods and requires this complete set of 25 initializers. A
separate code-region scan found no external relative branch into these handlers.
A native death action that does not create an explosion remains that action;
this modification does not make every disappearing object explode.

Each wrapper calls its unchanged native SH2 handler first. Position, velocity,
projection, lifetime, unlinking and completion counters remain SH2 operations.
The wrapper stops immediately when the native handler frees the object. The
boss controller at `0x139396` retains its original particle creation and counter
logic. Animation initialization is deferred until the first native update for
the 24 direct initializers; it does not run the native motion twice.

An initializer may be drawn before that first update. The five native explosion
descriptors at `0x744`–`0x7B1` therefore already select the shared SH1 graphics,
with the appropriate geometry, and direct initializers select palette bank 7.
The native descriptor families keep their three/two LOD counts for this initial
projection. Their source sizes map to donor LODs `(0,1,3)` and `(1,3)`; steady
updates use all four donor sizes. Geometry for each donor size is identical
across the eleven poses, so these initial descriptors also work with a warm cache.

## Artwork, animation and native movement

The original eleven poses each contain four source sizes: 16×16, 48×40, 80×64
and 112×88. All 44 images, their composition records and palette come from the
authenticated local SH1 ROM. No synthesized or rescaled source frames are added.
Only generated adapters are distributed; no SH1 movement or cleanup code is
copied into the port.

All modified explosions share the animation cache and clock rule. Creation
resets the shared phase, the next update initializes its quotient, and later
poses advance when `game_clock >> 2` changes. The last pose is held while a native
SH2 object remains alive. A warm creation preserves the current pixels until
its first update; a cold generic constructor preloads defined pixels. Pending
wrappers upload only once during their first update. Short boss particles can
expire before all eleven poses appear, and repeated creation can restart the
shared animation before it finishes.

SH2 still brings ordinary airborne explosions toward the ground in four game
updates, approximately 0.13 seconds. This is its original movement. The earlier
transplant's extra ground overshoot and lost depth update remain corrected.
Palette color 8 keeps its independent six-step cycle, updated through the eleven
verified game-clock increment sites. See [the timing reference](SH2_EXPLOSION_TIMING.md).

## Permanent graphics allocation

The previous high-end cache overlapped dense stage-three graphics. Its guard
then returned effects to the native artwork: the reproduced v0.1.13 run had one
activation and six fallbacks. Simply expanding the actor list would not fix it.

Version 0.1.14 replaces the original common explosion allocation instead. Its
212 native tiles become 268 donor tiles. The common loader at `0xAF724` records
the actual cache base, loads all four donor sizes and initializes the extended
palette. The second native explosion-family upload is skipped. Later common
assets and wave allocations move forward by exactly 56 tiles (1,792 bytes).

The native immediate wave base changes from 978 to 1,034 at both fixed reset
sites. The bytecode's absolute cursor reset at `0x191BFA` adjusts addresses at
or after the old common end, 972, by 56. Saved cursors already contain the new
addresses and are restored unchanged. This adapter preserves registers and the
original MOVE's condition codes, including X. Allocation remains within the
original 2,048-tile graphics bank; emulated video memory is not enlarged.

The cache recorded in all validation runs starts at tile 740, covering
`0xD15C80`–`0xD17DFF`. Its address is captured from the loader, not assumed by
animation code. Subsequent wave loads cannot reclaim this common allocation.
The guard only detects an uninitialized common cache; it no longer rejects an
explosion because unrelated assets extend beyond the former high-end limit.

| Area | Purpose |
| --- | --- |
| `0x380100`–`0x3808FF` | Generic constructor, native-first updates, ordinary pending wrapper, trampoline and palette clock |
| `0x380A00`–`0x380EFF` | Initialization, particle/tracked pending wrappers and LOD selector |
| `0x381000` | Shared animation and image upload |
| `0x381200`, `0x381280` | Common cache initialization and absolute cursor relocation |
| `0x382000`, `0x382400` | Donor descriptors and piece geometry |
| `0x384000`–`0x39B07F` | 94,336 bytes of image payloads read from the local donor |
| `0x39C000` | Palette read from the local donor |
| RAM `0xFE0000`–`0xFE0015` | Cache address, animation state and diagnostic counters |
| RAM `0xFE0100` | Extended tile-slot table, four added slots `0x180`–`0x183` |
| CRAM entries 112–127 | Extended palette bank 7 |

All 190 original tile-table references are relocated. Instruction signatures,
original slot identities and donor bounds are validated before applying the
patch transactionally. Original SH2 ROM pixel bytes remain unchanged; the five
native explosion descriptors are redirected to the imported resources.

## Validation and limits

[SH2_EXPLOSION_V014_VALIDATION.json](SH2_EXPLOSION_V014_VALIDATION.json) records
the exact tested core and results. Twelve independently selected stages each
ran for 18,000 frontend steps with scripted movement and firing. Lives were held
at nine only to continue the diagnostic. These runs observed 129 activations,
zero fallbacks and a maximum cursor of 2,018, below 2,048. Only the common loader
and the SH1 animation uploader wrote to the reserved cache. Stage 12 exercised
its graphics and boss approach but produced no destruction in this input run.
These are coverage samples, not twelve completed stages or every boss defeated.

The stage-three reproduction observes twelve modified effects without a
fallback. A forced-position diagnostic verifies all eleven poses and 29 complete
cache uploads, matching all 44 source images byte for byte. A separate controlled
native boss death still creates and removes 21 particles at their native age
limits, finishes its controller at age 41, and decrements its counter once.
The modified burst completes 22 video frames later because additional guest
instructions take time; this experimental-mode cost remains.

Original-mode SH2 and SH1 retain their measured baseline video/PCM. Runtime
Original → SH1 → Original → SH1 changes, threaded operation, autosaves, fixed
state-buffer capacity and legacy original-state loading pass. Active stage-three
and stage-four states reproduce their following video and audio.

Historical measurements remain in
[the v0.1.13 manifest](SH2_EXPLOSION_V013_VALIDATION.json) and
[the v0.1.12 manifest](SH2_EXPLOSION_VALIDATION.json). The modification remains
optional and disabled by default. Source artwork and animation rules are
verified; identical wall-clock/raster timing or complete-game coverage is not
claimed for the enabled mode.
