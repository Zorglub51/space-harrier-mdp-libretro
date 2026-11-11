# Mark V on TrimUI Smart Pro with NextUI

1. Extract the archive at the root of the microSD card. Replace the earlier
   MARKV and Mark V Benchmark paks if present. The emulator goes in
   `Emus/tg5040/MARKV.pak` and the benchmark goes in `Tools/tg5040/Mark V Benchmark.pak`.
2. Create `Roms/Space Harrier (MARKV)` on the card and copy your original
   Space Harrier and Space Harrier II `.smp` files there.
3. Open **Space Harrier** in NextUI, launch either game, and press **Start**.
   Open **Menu > Options > Emulator** to change **FM Level**, **PCM Level**,
   **PSG Level**, **Widescreen (16:9)** or **Mark VI**. Use **Aspect** screen
   scaling in NextUI for the core's intended proportions. Enable
   **Menu > Options > Frontend > Debug HUD** to check the displayed frame rate
   while playing. If launch fails, collect `.userdata/tg5040/logs/MARKV.txt`.
4. Run **Tools > Mark V Benchmark**. Use the same CPU speed setting and governor
   as for the previous benchmark. Wait for the tool to return to the menu.
5. Retrieve `MarkV-Benchmark.txt` from the card root. Check for `Benchmark complete`
   and include both games' results and the governor and frequency lines.

To check the Space Harrier fixes, open **Options > Music Test > Main Theme**
and play the track for at least 20 seconds. The intro has a sustained chord
and bass under the drums. The lead enters around 12 seconds in. Then restart
Space Harrier and leave it at the title screen without input for at least
three minutes to cover the stage 15 attract demo.

The machine benchmark runs 4,200 frames per ROM with scripted controller input,
first at the default settings and then with Mark VI and Widescreen enabled.
It measures the 68000, Z80, bus, renderer and sound synthesis together. In the
second run, `mark_vi_sprite_peak` is the largest reconstructed list observed
at a frame boundary.
The log reports the stereo sample count and peak amplitude to confirm audio output.
Look at p95 and p99 against the 16.69 ms native frame budget and compare with
the previous build. Display, audio resampling and frame pacing run in NextUI.

The private archive also includes the same 48 raster recordings per game as the
previous standalone benchmark. Compare its **Replay with VRAM reconstruction**
p95 and p99 with the previous benchmark's **Render** times. Each run first checks
every captured pixel and raw sprite sample. Keep the archive containing those
recordings private. Both archives require your own ROM files.
