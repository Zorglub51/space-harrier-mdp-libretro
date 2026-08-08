# Troubleshooting

## The core is not listed

Make sure the shared library and `shmdp_libretro.info` are both in RetroArch's
configured **Cores** directory. Use `.dll` on Windows, `.dylib` on macOS and `.so`
on Linux, from the archive matching your architecture.

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
