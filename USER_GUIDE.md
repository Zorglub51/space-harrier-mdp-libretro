# User guide (English)

## You will need

1. A 64-bit Windows, macOS or Linux computer.
2. [RetroArch](https://www.retroarch.com/) installed.
3. Your own original SH1 or SH2 file, extracted from hardware you own.
4. The `space-harrier-mdp-….7z` archive for your operating system from this
   repository's **Releases** page.

Extract the complete archive with 7-Zip or a compatible tool. On Mac, choose
`macos-arm64` for Apple Silicon or `macos-x86_64` for Intel. The `source` archive
is only needed for rebuilding. Each release has version notes and an included
`CHANGELOG.md`.

No ROM is included. The same core supports both originals:

| Game | File | Size | SHA-1 |
| --- | --- | --- | --- |
| SH1 | `jp_jp_space_harrier.smp` | 4,063,232 bytes | `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72` |
| SH2 | `jp_jp_Space_Harrier_II.smp` | 3,670,016 bytes | `80f576af01d6413c0b92073e2f947b0431f12a74` |

On Windows, use `TESTER_SH1_WINDOWS.cmd` or `TESTER_SH2_WINDOWS.cmd` to choose
RetroArch and the original ROM. Each launch keeps its logs and screenshots in
a separate session directory.

## Install the core

### Automatic installation on macOS

1. Quit RetroArch completely.
2. Extract the macOS archive.
3. Double-click `INSTALLER_MACOS.command`. If macOS blocks it, right-click the
   file and choose **Open**.
4. Restart RetroArch.

The installer reads RetroArch's configured directories, puts each file in the
correct location and rebuilds the core-info cache. It does not touch ROMs,
saves, or any other core.

### Manual installation on any system

1. Extract the downloaded archive.
2. In RetroArch, open **Settings > Directory** and note both the **Cores** and
   **Core Info** directories.
3. Close RetroArch.
4. Copy `shmdp_libretro.dll` (Windows), `shmdp_libretro.dylib` (macOS), or
   `shmdp_libretro.so` (Linux) into the **Cores** directory.
5. Copy `shmdp_libretro.info` into the separate **Core Info** directory, then
   do not put the `.info` file in **Cores**.
6. Delete the generated `core_info.cache` file from **Core Info** if it exists.
   RetroArch will recreate it automatically.
7. Restart RetroArch.

The usual macOS locations are:

- library: `~/Library/Application Support/RetroArch/cores/`;
- `.info` file: `~/Library/Application Support/RetroArch/info/`.

Some RetroArch versions also let you select **Load Core > Install or Restore a
Core** and choose the extracted core library directly. This does not always
install the `.info` file or rebuild the cache, so perform steps 5 and 6 yourself
if needed.

## Play

Select **Load Core > Space Harrier MDP**, then **Load Content** and choose the
original `.smp` file. The core recognises it and applies the repairs in memory;
the file on disk is never changed.

The directional pad or left stick moves Harrier, RetroPad **B** fires and **Start**
starts the game. Remap these under **Quick Menu > Controls > Port 1 Controls** if
needed.

See [Troubleshooting](docs/TROUBLESHOOTING.md) if the core or game does not load.

## Native Deflicker options

Under **Quick Menu > Core Options > Emulation Hacks**, choose **SH1 Deflicker
(Native)** or **SH2 Deflicker (Native)**. Each game has its own setting:

- **Game Setting** (default): let the original in-game setting control the mode.
- **OFF**, **ON1**, **ON2**: select that original sprite-list strategy directly.

Changes take effect during gameplay without restarting. ON1 and ON2 can reduce
flicker, but may omit sprites; they reproduce the original tradeoffs. No image
filter, frame blending or sprite persistence is added. The underlying in-game
choice is retained, and **Game Setting** returns control to it.

The core preference also applies after a reset or a save-state load. Keep the
same Deflicker selection when you want an identical replay of a saved sequence.
Save-state formats are unchanged, including the 0.1.14 SH1-explosion mode.

## Optional SH1 explosions in SH2

Put your original `jp_jp_space_harrier.smp` next to the SH2 ROM, or in
RetroArch's **System/BIOS** directory. In **Quick Menu > Core Options >
Emulation Hacks**, set **SH2 Explosions** to **SH1 Artwork and Timing**.
Changing this option automatically restarts SH2 from the beginning when gameplay
resumes. The replacement covers all exploding objects, including enemies, bosses,
scenery and explosions caused by player collisions. It no longer filters by
enemy family. The graphics cache is reserved within the game allocation, fixing
the stage-three returns to the original artwork.

The default is **Original SH2**. Choose it to restart with the original effects.
This feature reads its artwork and palette from the SH1 ROM and reproduces the
source animation cadence. No game graphics are included in the core. Neither ROM file is modified.
An absent or unsupported SH1 ROM leaves the original animation active and
displays a message. SH1 itself is unaffected by this option.

Save states belong to the selected mode: the core rejects a state from the
other mode. Modified-mode states from 0.1.12 and 0.1.13 are incompatible with 0.1.14.
MAME automatic saves use a separate folder for the modified mode. Switching the
option starts a fresh game rather than resuming an automatic save.

Ordinary explosions descend rapidly toward the ground in original SH2 as well.
The modification keeps SH2's positions, movement and removal rules while using
SH1's graphics and pose cadence.

This optional modification is experimental. Its extra guest instructions can
slow dense effects: a controlled boss burst delayed its completion by 22 video
frames (about 0.37 seconds). Boss particles can disappear before displaying all
eleven SH1 poses because they retain SH2's lifetime. Earlier measurements on
0.1.12 also found small introduction-image and audio-sample differences; an
audible difference has not been established. Keep **Original SH2** for the
unmodified experience.
