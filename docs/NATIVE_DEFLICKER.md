# Native SH1 and SH2 Deflicker core options

Version 0.1.15 exposes two independent options under **Emulation Hacks**:

| Core option | Values | Default |
| --- | --- | --- |
| `mame_sh1_deflicker` / SH1 Deflicker (Native) | `game`, `off`, `on1`, `on2` | `game` |
| `mame_sh2_deflicker` / SH2 Deflicker (Native) | `game`, `off`, `on1`, `on2` | `game` |

`game` delegates to the stored in-game setting. The other values select native
modes 0, 1 and 2. The ROM itself changes sprite-list construction. This does not
add a postprocessing filter, blend successive images, retain omitted sprites or
change the renderer's sprite limits. The native ON1/ON2 tradeoffs can include
omitted objects; neither is a promise of flicker-free output.

## Native setting identification

Both original ROMs contain DEFLICKER and OFF/ON1/ON2 menu strings. The SH1 setting
was previously traced independently of the separate EXTENDS and menu-visibility
bytes. The SH2 setting was identified through the menu's three-entry string
lookup, its increment/decrement handlers and its sprite-list consumers.

| Game | Setting byte | Menu lookup | Native sprite-list reads |
| --- | --- | --- | --- |
| SH1 | `0xFF3C36` | Table at `0xFF1510` | Instructions at `0x170366`, `0x17048C`, `0x1707A2` |
| SH2 | `0xFF2E62` | Instruction `0x0A084C`, table at `0xFF0FB0` | Instructions at `0x13B07A`, `0x13B1A0`, `0x13B4B4`; additional mode comparison at `0x13B53C` |

SH2 clears the byte at `0x09D168`. Its menu cycles the three values through
`0x0A1074`, `0x0A1812`, `0x0A1CDC` and `0x0A21B6`. Diagnostic CPU PCs reported
by memory taps can point just after an instruction; the addresses in the table
are the instruction starts, checked against the original operand bytes.

The public private-ROM test checks authenticated ROM identities, setting operands
and menu labels without copying game bytes into fixtures.

## Integration and state behavior

The cartridge loader records SH1 or SH2 only after the existing SHA-1-checked
compatibility adapter accepts the ROM. Other cartridges do not receive a tap.
After machine reset, the console driver installs a read tap on the setting word.
Both settings occupy the high byte of a big-endian word; the low neighboring byte
and inactive byte lanes are preserved.

Frontend options are atomic preferences. At each native read an explicit choice
replaces only the returned setting byte. No per-frame RAM write or guest patch is
needed. Missing, unknown and `game` values return the unmodified game value.
Changing a preference requires no content reload and does not overwrite the
stored in-game choice. Native menu operations can still change that stored choice;
while overridden, its displayed/consumed value follows the core option.

The tap is replaced on reset. Preferences remain outside emulated state, like
other core settings, so a loaded state uses the current preference. Returning to
Game Setting uses the setting stored by the game or loaded from the state. No
save items or state-envelope versions change; the 0.1.14 explosion-mode format 3
and its namespace are retained. Use the same option when expecting an identical
save-state replay.

## Validation

[NATIVE_DEFLICKER_VALIDATION.json](NATIVE_DEFLICKER_VALIDATION.json) records the
exact macOS arm64 candidate and 21 integration runs:

- Eight v0.1.14 reference runs: each game with its normal setting, then its native
  RAM byte selected as 0, 1 or 2. Lua writes the reference setting from frame 120;
  the new core does not use this mechanism.
- Eight candidate comparisons: 4,000 frontend steps for Game Setting/OFF/ON1/ON2
  in each game, plus a 120-step save/load replay. Video and PCM hashes match the
  corresponding reference. Selecting ON2 for the other game leaves Game Setting
  output unchanged.
- Three threaded runtime sequences: both games, plus SH2 with SH1 explosions.
  Game Setting → ON1 → ON2 → OFF → Game Setting reads back 0/1/2/0/0 without
  restarting. Each change includes a save/load replay. A subsequent explicit
  reset retains ON2 and also passes replay. The diagnostic script restarts only
  at initial load and the requested reset.
- Two missing/invalid-setting runs preserve the default reference output.

Libretro option registration was inspected for both the legacy interface and
version 2: both options, all four values and the Game Setting default are exposed.
The configured suite runs 111 tests: 99 pass and 12 optional native-reference
checks are skipped. The setting-byte tests cover both byte lanes, word/partial
accesses and invalid modes.

These sampled sequences demonstrate that the frontend selects the existing ROM
behavior. They do not establish complete-game coverage or a new pixel-perfect
comparison against m2engage in every Deflicker mode.
