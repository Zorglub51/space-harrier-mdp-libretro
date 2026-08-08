# User guide (English)

## You will need

1. A 64-bit Windows, macOS or Linux computer.
2. [RetroArch](https://www.retroarch.com/) installed.
3. Your own original `jp_jp_space_harrier.smp`, extracted from hardware you own.
4. The `space-harrier-mdp-…zip` archive for your operating system from this
   repository's **Releases** page.

No ROM is included. The supported original is exactly 4,063,232 bytes and has
SHA-1 `e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`.

## Install the core

1. Extract the downloaded archive.
2. In RetroArch, open **Settings > Directory** and note both the **Cores** and
   **Core Info** directories.
3. Close RetroArch.
4. Copy `shmdp_libretro.dll` (Windows), `shmdp_libretro.dylib` (macOS), or
   `shmdp_libretro.so` (Linux) into the **Cores** directory.
5. Copy `shmdp_libretro.info` into the separate **Core Info** directory, then
   restart RetroArch. Do not put the `.info` file in **Cores**.

The usual macOS locations are:

- library: `~/Library/Application Support/RetroArch/cores/`;
- `.info` file: `~/Library/Application Support/RetroArch/info/`.

Some RetroArch versions also let you select **Load Core > Install or Restore a
Core** and choose the extracted core library directly. This does not always
install the `.info` file, so copy that file to **Core Info** yourself if needed.

## Play

Select **Load Core > Space Harrier MDP**, then **Load Content** and choose the
original `.smp` file. The core recognises it and applies the repairs in memory;
the file on disk is never changed.

The directional pad or left stick moves Harrier, RetroPad **B** fires and **Start**
starts the game. Remap these under **Quick Menu > Controls > Port 1 Controls** if
needed.

See [Troubleshooting](docs/TROUBLESHOOTING.md) if the core or game does not load.
