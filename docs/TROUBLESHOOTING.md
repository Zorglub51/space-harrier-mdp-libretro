# Troubleshooting

## The core is not listed

Make sure the shared library is in RetroArch's configured **Cores** directory
and `shmdp_libretro.info` is in the separate **Core Info** directory. Both paths
are shown under **Settings > Directory**. Use `.dll` on Windows, `.dylib` on
macOS and `.so` on Linux, from the archive matching your architecture.

If the core is still listed by filename, quit RetroArch, delete the generated
`core_info.cache` file from **Core Info**, and restart. The cache is rebuilt
automatically.

## The game does not start

Use the untouched 4,063,232-byte original with SHA-1
`e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72`. Load **Space Harrier MDP** first,
then the `.smp` content. With RetroArch debug logging enabled, a successful launch
prints `Applied the Space Harrier MDP compatibility patch in memory`.

## macOS blocks the library

This community core is not Apple-signed. Allow it under **System Settings >
Privacy & Security** if macOS offers that choice. A sandboxed RetroArch package
may not allow external cores; use an installation that supports local cores.

## Wrong speed

Disable fast-forward, slow motion and rewind. Keep audio synchronisation enabled
and use the core's normal frame rate.

## Reporting a bug

Include OS, architecture, RetroArch/core versions, the exact point in the game, a
screenshot or short video, and a verbose RetroArch log. Never upload the ROM.

### Windows crashes in 0.1.16 and later

This report remains under investigation. A passing compilation or startup test
does not establish that the reported gameplay configuration works on Windows 10.
The measured checks and their limits are recorded in
[WINDOWS_RUNTIME_VALIDATION.json](https://github.com/Zorglub51/space-harrier-mdp-libretro/blob/main/docs/WINDOWS_RUNTIME_VALIDATION.json).

To obtain a reproducible log, extract the affected release into a new folder
and run `TESTER_SH1_WINDOWS.cmd` or `TESTER_SH2_WINDOWS.cmd`. Select the same
RetroArch x64 executable and the original game ROM. Each launcher creates an
isolated `session/` directory with default core settings and no automatic state
loading. Preserve existing saves and configuration.

Send `logs/retroarch.log` and `session.json` from that session, the launcher's
exit code if shown, the Windows/RetroArch versions, CPU model, game and exact
point of failure. If this isolated run succeeds, also provide the options used
by the failing installation. If Windows records an Application Error, include
its faulting module, exception code and fault offset. Do not send the whole
session directory, ROMs or save-state files.
