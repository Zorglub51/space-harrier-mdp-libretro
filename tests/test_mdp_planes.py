"""Compare the shipped transformed-plane renderer with original M2 ARM output.

Only memory and the two MAME composition buffers are stubbed. The sampled C++
method and its VRAM accessor come from the public patch, not a test rewrite.
Synthetic tiles exercise coordinates, banks, palette, flips and transparency;
no game ROM or original executable is needed to run the committed fixtures.
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
FIXTURE = ROOT / "tests/fixtures/mdp_planes_m2.json"
FIELDS = ("control", "h", "v", "line", "xoff", "sx", "sy", "dx", "dy",
          "vx", "vy", "attr_flags", "old", "texture", "plane")

PROBE = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using s16 = std::int16_t;
using s32 = std::int32_t;
#define BIT(value, bit) (((value) >> (bit)) & 1U)
class sega315_5313_device {
public:
    u16 m_regs[64] = {};
    u16 m_vram[0x8000] = {};
    u16 m_mdp_ram[0x8000] = {};
    u16 *m_mdp_scaler = m_mdp_ram;
    u32 m_video_renderline[320] = {};
    u8 m_highpri_renderline[320] = {};
    VRAM_ACCESSOR
    void mdp_scaler_line(int scanline, int plane, u16 base, int first, int last);
    void word(unsigned byte, u16 value) {
        (byte < 0x10000 ? m_vram[byte / 2] : m_mdp_ram[(byte - 0x10000) / 2]) = value;
    }
    void fixed(unsigned byte, u32 value) {
        word(byte, value >> 16);
        word(byte + 2, value);
    }
};
PLANE_FUNCTION
int main() {
    int ctl, h, v, line, first, sx, sy, dx, dy, vx, vy, flags, old, texture, plane;
    if (!(std::cin >> ctl >> h >> v >> line >> first >> sx >> sy >> dx >> dy
          >> vx >> vy >> flags >> old >> texture >> plane)) return 2;
    sega315_5313_device vdp;
    vdp.m_regs[32 + plane] = ctl;
    vdp.m_regs[16] = h | (v << 4);
    for (int i = 0; i < 320; ++i) {
        vdp.m_video_renderline[i] = 0x12345;
        vdp.m_highpri_renderline[i] = 0x6f;
    }
    for (int i = first; i < first + 8; ++i) {
        vdp.m_video_renderline[i] = old & 0x3f;
        vdp.m_highpri_renderline[i] = (old & 0x8000) ? ((old & 0x3f) | 0x80) : (old & 0x80);
    }
    // Same synthetic VRAM recipe used by MdpPlaneOracle.java, version 1.
    for (int tile = 1; tile <= 15; ++tile) {
        for (int y = 0; y < 8; ++y) {
            for (int half = 0; half < 2; ++half) {
                u16 packed = 0;
                for (int p = 0; p < 4; ++p) {
                    const int x = half * 4 + p;
                    int colour = texture == 0 ? tile : 1 + ((tile - 1 + x + 3 * y) % 15);
                    if (texture == 2 && (x + y) % 3 == 0) colour = 0;
                    packed = (packed << 4) | colour;
                }
                vdp.word(tile * 32 + y * 4 + half * 2, packed);
            }
        }
    }
    const int shifts[] = {5, 6, 0, 7};
    const int columns = 1 << shifts[h], rows = 1 << shifts[v];
    for (int y = 0; y < rows; ++y)
        for (int x = 0; x < columns; ++x)
            vdp.word(0x8000 + (y * columns + x) * 2, flags | (1 + (x + 3 * y) % 15));
    const unsigned table = (ctl & 31) << 12;
    for (int y = 0; y < 240; ++y) {
        const unsigned entry = table + y * 16;
        vdp.word(entry, 4096);
        vdp.word(entry + 2, 0);
        vdp.fixed(entry + 8, 0);
        vdp.fixed(entry + 12, ((y + 7) % 32) * 8 * 4096);
    }
    const unsigned entry = table + ((ctl & 32) ? line * 16 : 0);
    vdp.word(entry, dx);
    vdp.word(entry + 2, dy);
    vdp.word(entry + 4, vx);
    vdp.word(entry + 6, vy);
    vdp.fixed(entry + 8, u32(sx));
    vdp.fixed(entry + 12, u32(sy));
    vdp.mdp_scaler_line(line, plane, 0x8000, first, first + 8);
    for (int i = 0; i < 320; ++i) {
        if (i < first || i >= first + 8) {
            if (vdp.m_video_renderline[i] != 0x12345 || vdp.m_highpri_renderline[i] != 0x6f)
                return 3; // Window clipping must preserve surrounding pixels.
            continue;
        }
        const u16 high = vdp.m_highpri_renderline[i];
        // Convert MAME's two plane buffers to M2's single intermediate word.
        // Transparent high-priority tiles retain the previous colour and set
        // bit7; they do not acquire the opaque priority bit15.
        const u16 pixel = (high & 15) ? (0x8000 | high)
            : ((vdp.m_video_renderline[i] & 0x3f) | (high & 0x80));
        std::cout << pixel << ' ';
    }
    std::cout << '\n';
}
"""


def probe_source(patch):
    cpp = patched_fragments(patch, "src/devices/video/315_5313.cpp")
    header = patched_fragments(patch, "src/devices/video/315_5313.h")
    return (PROBE.replace("VRAM_ACCESSOR", full_function(header, "u16 mdp_vram_word("))
            .replace("PLANE_FUNCTION", full_function(cpp, "void sega315_5313_device::mdp_scaler_line(")))


class MdpPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory / "mdp_plane_probe.cpp"
        source.write_text(probe_source(PATCH.read_text()), encoding="utf-8")
        cls.probe = directory / ("mdp_plane_probe.exe" if os.name == "nt" else "mdp_plane_probe")
        subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
            str(source), "-o", str(cls.probe),
        ], check=True)

    def run_case(self, inputs):
        result = subprocess.run([str(self.probe)],
                                input=" ".join(str(inputs[field]) for field in FIELDS) + "\n",
                                text=True, capture_output=True, check=True)
        return list(map(int, result.stdout.split()))

    def compare_reference(self, reference, predicate=lambda case: True):
        self.assertEqual(reference["schema"], 1)
        self.assertEqual(reference["source"]["renderer_file_offset"], 0xb1bc0)
        self.assertEqual(reference["source"]["synthetic_vram_recipe"], 1)
        self.assertEqual(reference["source"]["binary_sha256"],
                         "2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f")
        cases = [case for case in reference["cases"] if predicate(case)]
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(self.run_case(case["input"]), case["pixels"])

    def test_coordinates_banks_and_modes_match_original_arm(self):
        self.compare_reference(json.loads(FIXTURE.read_text()),
                               lambda case: case["input"]["texture"] != 2)

    def test_transparency_preserves_underlying_colour_and_priority(self):
        self.compare_reference(json.loads(FIXTURE.read_text()),
                               lambda case: case["input"]["texture"] == 2)

    def test_fresh_original_arm_run_when_configured(self):
        path = os.environ.get("MDP_PLANE_ORACLE_JSON")
        if not path:
            self.skipTest("MDP_PLANE_ORACLE_JSON is not configured")
        self.compare_reference(json.loads(Path(path).read_text()))

    def test_disabled_transform_preserves_existing_plane(self):
        inputs = dict(json.loads(FIXTURE.read_text())["cases"][0]["input"])
        inputs.update(control=0x70, old=0x80ae)
        self.assertEqual(self.run_case(inputs), [0x80ae] * 8)


if __name__ == "__main__":
    unittest.main()
