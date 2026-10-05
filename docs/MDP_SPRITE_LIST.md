# M2 sprite selection and rendering

Version 0.1.8 replaces the port's empirical sprite pixel budget and inherited
Mega Drive selection rules with a dedicated MDP sprite path. It reads the
current SAT directly from VRAM and follows the original M2 renderer at `C1E24`.
SH1 and SH2 use this same path.

## Native selection rules

M2 walks the seven-bit linked list from entry zero. It marks each entry visited
before checking its vertical intersection and stops before visiting an entry a
second time. A chain can therefore traverse all 128 entries, including entries
outside the current line. SAT word addresses use
`((reg5 & 0x7f) << 8) | (index << 2)`. The OR is significant: an odd table base
can alias entry 64 with entry zero. The port previously used a masked H40 base
and a separate Mega Drive attribute cache.

The limits depend on the active width:

| Active width | Selected sprites | Source columns |
|---|---:|---:|
| 256 pixels | 16 | 32 |
| 320 pixels | 20 | 40 |

Each selected sprite consumes its source width in eight-pixel columns. Zoom,
transparency and horizontal clipping do not reduce this cost. A sprite with zero
vertical extent is not selected. An X coordinate whose low nine bits are zero
terminates selection only when that sprite intersects the current line; it also
terminates the list when it is the first entry. The inherited Mega Drive rule
involving an additional sprite with X below 64 does not apply.

M2 draws the selected entries in reverse order and overwrites nontransparent
pixels. Thus an earlier SAT entry wins a sprite overlap regardless of its plane
priority bit. Transparent pixels preserve pixels already drawn.

The first entry drawn, which is the last one selected, is limited to the
remaining column count. Later entries can draw up to their full four columns.
This includes a measured M2 quirk: when a chain ends naturally at 39 source
columns, its final three-column sprite can draw only one column. The port
reproduces this result rather than adjusting the budget to a more conventional
interpretation.

## Geometry and tile fetch

The existing M2 zoom and reduction contracts remain in effect. When register 36
bit 7 is set, it selects the transform bank and enables the MDP source-bank and
upper-palette size bits. With this bit clear, the original renderer takes its
ordinary sprite path and ignores those size bits. Interlace bits in register 12
do not alter M2's sprite geometry in the tested paths.

Tile-row and column increments apply to the complete attribute word, matching
the native carry behaviour at tile and attribute boundaries. The reduction
lookup operates on each cell separately, retaining M2's asymmetric left-edge
clipping. Pixel decoding now reads the unified VRAM words directly, so it does
not depend on a stale decoded tile or attribute cache.

## Reproduction and coverage

`scripts/ghidra/MdpSpriteListOracle.java` executes the original ARM renderer on
synthetic VRAM. It stops at `C2472`, before plane/sprite composition and NEON
palette conversion. The only intercepted external operation is `memset`.

```sh
"$GHIDRA_HOME/support/analyzeHeadless" "$PROJECT_DIR" "$PROJECT_NAME" \
  -process m2engage -noanalysis -readOnly \
  -scriptPath "$REPOSITORY/scripts/ghidra" \
  -postScript MdpSpriteListOracle.java /tmp/mdp-sprite-list.json

MDP_SPRITE_LIST_ORACLE_JSON=/tmp/mdp-sprite-list.json \
  python3 -m unittest discover -s tests -p 'test_mdp_sprite*.py' -v
```

The script verifies the reference binary SHA-256 and uses fixed loaded addresses.
The public fixture contains 76 synthetic cases and every native sprite pixel.
Cases cover both widths and both zoom modes, limits, cycles, all 128 links,
zero X, offscreen and transparent entries, overlap order, table aliasing,
interlace bits, graphics and palette banks, attribute carries and reduced cells.
The C++ test extracts and compiles the complete production method from the
public patch. Earlier geometry, zoom-bank and clipping fixtures are also replayed
through that same method; the old inactive rendering path is not used as proof.

A captured SH2 scene near the first boss, at reference frame 6600, supplies an
additional integration check. Its 224 lines were executed by the original
renderer. Version 0.1.7 differs in 30 of the 71,680 indexed pixels, on six lines;
all differences are already present in its sprite layer. Three lines with an
upper-VRAM mutation were replayed using both snapshots and produced identical
native outputs. Final candidate results are recorded in the
[validation manifest](MDP_SPRITE_LIST_VALIDATION.json). These checks do not
establish complete CPU timing or every game scene.
