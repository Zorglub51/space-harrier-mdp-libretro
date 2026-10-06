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

## Optional SH1 explosions in SH2

Put your original `jp_jp_space_harrier.smp` next to the SH2 ROM, or in
RetroArch's **System/BIOS** directory. In **Quick Menu > Core Options >
Emulation Hacks**, set **SH2 Enemy Explosions (Restart Required)** to
**SH1 Artwork and Timing**, then close and reload the content. The ordinary
**Restart** command only resets the running machine; it does not reload the ROM.

The default is **Original SH2**. Choose it and reload to disable the patch.
This feature uses the SH1 ROM as the source of its artwork and animation code;
no game graphics are included in the core. Neither ROM file is modified.
An absent or unsupported SH1 ROM leaves the original animation active and
displays a message. SH1 itself is unaffected by this option.

Save states belong to the selected mode: the core rejects a state from the
other mode. MAME automatic saves use a separate folder for the modified mode.
Start a new game after switching the setting.

This optional modification is experimental. Its extra guest instructions can
cause small timing changes: the measured introduction differs briefly on
19 images, and the audio stream differs at sample level. An audible difference
has not been established. Keep **Original SH2** for the unmodified experience.
