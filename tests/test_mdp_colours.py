"""Compare the shipped MDP colour helper with the original RGB4440 callback.

The fixture exhausts all 4096 RGB nibble combinations in the original ARM
callback. C1E24 packs CRAM channels into those nibbles as c (shadow) or 2*c
(normal). This tests emulator output before host shaders or display filters.
"""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/mdp_colours_m2.json"
BINARY_SHA256 = "2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f"
PROBE = r"""
#include <cstdint>
#include <iostream>
using u16 = std::uint16_t;
struct rgb_t {
    unsigned packed;
    rgb_t(unsigned red, unsigned green, unsigned blue)
        : packed((red << 16) | (green << 8) | blue) {}
};
COLOUR_FUNCTION
int main() {
    for (int normal = 0; normal < 2; ++normal)
        for (unsigned cram = 0; cram <= 0xffff; ++cram)
            std::cout << mdp_indexed_pen(u16(cram), bool(normal)).packed << '\n';
}
"""


def probe_source(patch):
    cpp = patched_fragments(patch, "src/devices/video/315_5313.cpp")
    return PROBE.replace("COLOUR_FUNCTION", full_function(cpp, "static rgb_t mdp_indexed_pen("))


def native_index(cram, normal):
    """C1E24's normal/shadow LUT input, before the original colour callback."""
    red = (cram >> 1) & 7
    green = (cram >> 5) & 7
    blue = (cram >> 9) & 7
    return ((red << 8) | (green << 4) | blue) << int(normal)


class MdpColourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory / "mdp_colour_probe.cpp"
        source.write_text(probe_source(PATCH.read_text()), encoding="utf-8")
        executable = directory / ("mdp_colour_probe.exe" if os.name == "nt" else "mdp_colour_probe")
        subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
            str(source), "-o", str(executable),
        ], check=True)
        result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
        cls.actual = list(map(int, result.stdout.split()))
        cls.reference = json.loads(FIXTURE.read_text())

    def compare_reference(self, reference, cram_values):
        self.assertEqual(reference["schema"], 1)
        self.assertEqual(reference["source"]["binary_sha256"], BINARY_SHA256)
        self.assertEqual(reference["source"]["callback_file_offset"], 0x219e08)
        colours = reference["rgb888_by_rgb444"]
        self.assertEqual(len(colours), 4096)
        self.assertEqual(len(self.actual), 2 * 65536)
        for normal in (False, True):
            for cram in cram_values:
                self.assertEqual(self.actual[int(normal) * 65536 + cram],
                                 colours[native_index(cram, normal)],
                                 f"CRAM={cram:04x}, normal={normal}")

    def test_all_512_cram_colours_at_both_intensities_match_original_arm(self):
        crams = [((rgb & 7) << 9) | (((rgb >> 3) & 7) << 5)
                 | (((rgb >> 6) & 7) << 1) for rgb in range(512)]
        self.compare_reference(self.reference, crams)

    def test_unused_cram_bits_do_not_change_the_colour(self):
        self.compare_reference(self.reference, range(65536))

    def test_original_callback_ignores_low_nibble_and_upper_word(self):
        colours = self.reference["rgb888_by_rgb444"]
        cases = self.reference["ignored_bits"]
        self.assertEqual(len(cases), 19)
        for case in cases:
            self.assertEqual(case["rgb888"], colours[(case["input"] >> 4) & 0xfff])

    def test_fresh_original_arm_run_when_configured(self):
        path = os.environ.get("MDP_COLOUR_ORACLE_JSON")
        if not path:
            self.skipTest("MDP_COLOUR_ORACLE_JSON is not configured")
        reference = json.loads(Path(path).read_text())
        self.assertEqual(reference["rgb888_by_rgb444"], self.reference["rgb888_by_rgb444"])
        self.assertEqual(reference["ignored_bits"], self.reference["ignored_bits"])
        self.compare_reference(reference, range(65536))


if __name__ == "__main__":
    unittest.main()
