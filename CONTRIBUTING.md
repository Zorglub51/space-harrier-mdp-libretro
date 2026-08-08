# Contributing

Bug reports and test results from later stages are welcome. Never upload, commit or
link to copyrighted ROM data.

For a useful gameplay report, include:

- operating system and CPU architecture;
- RetroArch and core versions;
- whether the issue occurs in attract mode or manual play;
- stage and approximate time;
- exact reproduction steps, plus a short capture and verbose log if possible.

Source changes should keep the project pinned to the commit in `MAME_COMMIT` unless
the pull request deliberately rebases the complete patch. Before submitting:

```bash
bash -n scripts/*.sh
PYTHONPYCACHEPREFIX=/tmp/shmdp-pycache \
  python3 -m py_compile rompatch/patch.py scripts/generate_rom_patch_header.py
./scripts/fetch-mame.sh
./scripts/build-libretro.sh
```

Keep ROM reconstruction data in `rompatch/patch.py`; regenerate the in-memory C++
adapter through the existing script rather than maintaining a second patch table.
