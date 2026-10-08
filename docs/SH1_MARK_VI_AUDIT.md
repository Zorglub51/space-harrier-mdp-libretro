# SH1 Mark VI visibility audit

This audit distinguishes display limits from object lifetime and structural
visibility. Its reference is the original SH1 image with SHA1
`e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72` and the established reconstructed image
with SHA1 `718c21dc6e71e6a408bc35ebbe8ea755f3ad69e3`. No game assets or binary
dumps are included here.

## Constructor limits and flags

The constructor at `0x1702EC` takes the sorted object list at `FF40B8`, with
links at object offset `+18`. Its separate SAT partitions have native 40/80
entry budgets, and its transform counter stops at 128 (`1705C0`, `1705EA`).
Native Deflicker is byte `FF3C36`; its branches choose different partitioning
and overflow behavior. A host list built before those quotas need not force
Deflicker or modify the game's own lists.

Body visibility is tested at `1703C2..1703D2`: pose byte `+20` must be at most
`FD`, and bit `80` of byte `+2B` must be clear. The shadow pass has a different
rule: `1705F4..170606` checks the same pose but tests **word `+2A & 0084`**.
The shared `80` budget hides both; the independent `04` shadow flag must remain
effective when the budget is removed.

Tile references come from the allocation table at `FF3D16`. The generic
uploaders at `1E6870` and `1E6A82` iterate the descriptor count (`+0B`), not
visible-object or SAT counts. Their extended-memory paths copy each descriptor's
tile count (`+04`) from its data pointer (`+00`) to
`D10000 + (FF3C9A << 5)`, update the allocation entry selected by descriptor
ID (`+08`), and advance `FF3C9A`. The copy at `0C83D4` performs the complete
requested number of 32-byte tiles. The original-VDP path maps all descriptor
indices and uploads their total size. Explosion-phase loading at
`1D74A6..1D7512` likewise uploads every LOD in the selected animation phase.
These examined paths have no omission tied to SAT capacity or body flag `80`.
This is not proof that every stage's finite art-bank wrap and cache lifetime
has been exercised.

## Verified proximity thinning

There are six immediate setters of word `+2A` bit `0080` in the game's code.
Every one belongs to the following routines and has a depth/index predicate:

| Object routine | Set site | Clear site | Object register | Set condition |
| --- | --- | --- | --- | --- |
| `1246C8` | `1247E4` | `1247CC` | A2 | `FF3CB8 == 2`, index `+2C` bit 1 clear, signed depth `+0A <= 07FF` |
| `1247F0` | `124A4C` | `1248EC` | A2 | index bit 1 set, signed depth `<= 07FF` |
| `124AE4` | `124D88` | `124C1A` | A2 | index bit 1 set, signed depth `<= 07FF` |
| `124E20` | `12508C` | `124F2A` | A2 | index bit 1 set, signed depth `<= 07FF` |
| `12510E` | `125370` | `12520E` | A2 | index bit 1 set, signed depth `<= 07FF` |
| `1E41D8` | `1E42D0` | `1E42B8` | A1 | `FF3CB8 == 2`, index bit 1 clear, signed depth `<= 07FF` |

These are fixed reductions of nearby segment density, rather than a
frame-counter XOR. No setter is shared with a spatial overlap branch. The
setters, clearers, and their predicates are intact in the original image;
none of the six routine ranges contains an M2 native-hook entry.

The audit also scanned byte/word writes to `+2A/+2B` and overlapping long
writes. Register-based flag updates clear `0004` and set `0040`, or set
`0041`; they do not introduce `0080`. The one overlapping long store at
`1E6D3A` belongs to a separate SAT-node allocator, whose links are at
`+30/+34` and whose SAT index is at `+24`. It is not a world-object flag write.

`src/markv/sh1_visibility.h` removes only the recorded `0080` flag from a
body and shadow emission decisions for the six exact routine identities and
pose `<= FD`.
It does not recompute depth against a later game state, write the snapshot or
guest RAM, force a pose, or change the independent shadow flag `04`. A slot changed to the
retiring routines `12DF10` or `1E4E9A` is excluded. Their native clearers are
`12DF66` and `1E4EF0`, respectively.

## Hides that must remain

An opcode scan of the game-code range `0C0000..1FFFFF` found 259 `ST.B +20`
writes. Of these, 239 are immediately associated with unlinking the object and
putting it on the `FF3CA4` retirement/free list. The remaining 20 were inspected
in context; they include spawning, player presentation, structural overlap,
and terminal scene states. Treating all pose `FF` values as flicker would
restore deleted objects or expose pieces before their initialization.

- Harrier routines `1DD4E0` and `1DD698` deliberately hide the player at
  `1DD588` and `1DDA54`, based on bit 1 of their counter. These remain unchanged.
- Routine `1E4FBC` writes pose `FF` at `1E5018` for a spatially coincident child
  segment: signed depth at most `047F`, odd index at most 6, absolute projected
  horizontal distance at most 15 and vertical distance at most 7 from parent
  `+3A`. This is structural overlap, not temporal alternation.
- Routine `1E30F8` has parity-controlled event/score processing in terminal
  state 6, but both branches ultimately hide its body (`1E314C`, `1E31D6`,
  `1E3816`). That counter is not evidence of a visible blinking animation.
- The explicit pose `FE` write at `1DF360` targets the player object obtained
  through `FF16C8` during a scene transition. It is preserved.

No additional live, nonplayer temporal body-hide branch was established by
this static audit. That statement is bounded to the examined visibility
mechanisms; it is not an assertion that every possible palette animation,
graphics upload, game stage, or native rendering artifact has been validated.

## Verification

`tests/test_sh1_visibility.py` compiles the production helper and exercises all
65,536 flag words for each allowed routine, hidden/deleted poses, retiring
handlers, the player handlers, unknown/reused identities, and native shadow
visibility. Its assertions verify that only budget flag `0080` is removed and
that caller-owned flags stay unchanged. Runtime constructor comparisons and
full-core rendering tests are separate evidence.


## Private runtime diagnostics

The native remaining-lives counter is packed-BCD byte `FF1C04`.
Initialization at `0FB14E..0FB156` copies configured lives (`FF1C05`) minus one.
Harrier's death path at `1DD992` requests a pending delta of minus one through
longword `FF3CB0`; the update at `1392EA..1392F0` decrements the byte, with decimal
borrow handled at `1399FC..139A72`. Harrier tests for zero at `1DD958`. A private
keep-lives diagnostic can restore byte `FF1C04` to `09` after gameplay starts,
without changing collision, boss health, RNG, or object state.

The native title-stage selector uses byte `FF16CC`, stages 1 through 18. Its
Left/Right handlers at `0C6732` and `0C679C` require a nonzero flag at `FF3C40`
(`0C6728`). They decrement/increment the stage and wrap at `0C7D18`/`0C7D5C`.
Credit/title initialization resets the selected stage to 1 at `0C6952`.
No direct absolute write to the selector-enable flag was found in the game
image, so a diagnostic enabling it must explicitly record that additional
precondition; ordinary title input alone is not proven to enable it.

## Diagnostic stage selection used by the runtime tests

The title selector does not survive normal game startup: `1E5BEC` executes
`MOVE.B #1,FF16CC` before the stage initializer at `0FAC26` (called at `1E5BFC`).
The private-ROM regression harness uses native title Left/Right inputs,
temporarily enables `FF3C40`, and restores that enable byte before starting.
Its explicit `--stage` diagnostic transfers the selected title stage through
only this first startup write, guarded by the complete instruction bytes,
emulated PC `1E5BF4`, and the startup frame window. It records the native title
choice at frame 1250 and the in-game stage at frame 1400, and requires exactly
one transfer. Later stage transitions remain untouched. This test-only bus tap
is not part of the distributed core.
