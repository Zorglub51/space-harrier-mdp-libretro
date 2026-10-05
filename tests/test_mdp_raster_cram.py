"""Run the public patch's CRAM decoder against original M2 ARM observations.

The C++ probe uses the patched write method and raster flush prefix, with only
screen timing and ordinary VDP ports stubbed. No game ROM or MAME tree is needed.
Native fixtures prove decoding; scanline scheduling tests preserve the existing
port timing and do not claim a native M2 timing oracle.
"""

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "mame0289-space-harrier-mdp.patch"
FIXTURE = ROOT / "tests" / "fixtures" / "mdp_cram_m2.json"


def patched_fragments(patch, filename):
    """Collect the actual new side of this file's unified-diff hunks."""
    result, selected, in_hunk = [], False, False
    for line in patch.splitlines(keepends=True):
        if line.startswith("diff --git "):
            selected, in_hunk = False, False
        elif line.startswith("+++ "):
            selected = line.rstrip() == "+++ b/" + filename
        elif line.startswith("@@ "):
            in_hunk = selected
        elif in_hunk and line[:1] in {" ", "+"}:
            result.append(line[1:])
    return "".join(result)


def full_function(source, signature):
    start = source.index(signature)
    body = source.index("{", start)
    depth = 0
    for end in range(body, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise ValueError("Function is incomplete in public patch: " + signature)


PROBE = r"""
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using offs_t = std::uint32_t;
#define BIT(value, bit) (((value) >> (bit)) & 1U)
struct FakeScreen {
    int position = 0;
    int vpos() const { return position; }
    unsigned frame_number() const { return 0; }
};
struct FakeCpu { unsigned pcbase() const { return 0; } };
class sega315_5313_device {
public:
    DECLARATIONS
    u16 m_vdp_code = 0, m_vdp_address = 0;
    FakeCpu cpu;
    FakeCpu *m_cpu68k = &cpu;
    FakeScreen timing;
    FakeScreen &screen() { return timing; }
    void vdp_mdp_w(offs_t offset, u16 data, u16 mem_mask);
    void render_videoline_to_videobuffer(int scanline);
    void reset_raster() { RESET_STATEMENT }
    void write_cram_value(unsigned index, u16 data) {
        if (index >= 128) std::abort();
        std::cout << "C " << index << ' ' << data << '\n';
    }
    void vdp_w(offs_t offset, u16 data, u16 mask) {
        std::cout << "P " << offset << ' ' << data << ' ' << mask << '\n';
    }
};
WRITE_FUNCTION
FLUSH_FUNCTION
int main() {
    sega315_5313_device vdp;
    char command;
    while (std::cin >> command) {
        if (command == 'W') {
            int position;
            unsigned offset, data, mask;
            if (!(std::cin >> position >> offset >> data >> mask)) return 2;
            vdp.timing.position = position;
            vdp.vdp_mdp_w(offset, u16(data), u16(mask));
        } else if (command == 'R') {
            int line;
            if (!(std::cin >> line)) return 3;
            vdp.render_videoline_to_videobuffer(line);
        } else if (command == 'Z') {
            vdp.reset_raster();
        } else return 4;
    }
    return std::cin.eof() ? 0 : 5;
}
"""


def probe_source(patch):
    cpp = patched_fragments(patch, "src/devices/video/315_5313.cpp")
    header = patched_fragments(patch, "src/devices/video/315_5313.h")
    write = full_function(cpp, "void sega315_5313_device::vdp_mdp_w(")
    start = cpp.index("void sega315_5313_device::render_videoline_to_videobuffer(")
    end = cpp.index("\tgfx_element *tile_gfx", start)
    flush = cpp[start:end] + "}\n"
    declarations = re.findall(r"^\s*u(?:8|16)\s+m_mdp_raster_cram(?:_set)?\[[^;]+;", header, re.M)
    if len(declarations) != 2:
        raise ValueError("Expected both raster array declarations from the public patch")
    reset = re.search(r"memset\(m_mdp_raster_cram_set,\s*0,\s*sizeof\(m_mdp_raster_cram_set\)\);", cpp)
    if reset is None:
        raise ValueError("Expected raster reset code from the public patch")
    return (PROBE.replace("DECLARATIONS", "\n".join(declarations))
            .replace("RESET_STATEMENT", reset.group())
            .replace("WRITE_FUNCTION", write).replace("FLUSH_FUNCTION", flush))


class MdpRasterCramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory / "mdp_raster_probe.cpp"
        source.write_text(probe_source(PATCH.read_text()), encoding="utf-8")
        cls.probe = directory / ("mdp_raster_probe.exe" if os.name == "nt" else "mdp_raster_probe")
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        subprocess.run(compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                                   str(source), "-o", str(cls.probe)], check=True)

    def run_commands(self, commands):
        environment = os.environ.copy()
        environment.pop("MDP_NAMETAB", None)
        result = subprocess.run([str(self.probe)], input="\n".join(commands) + "\n",
                                text=True, capture_output=True, check=True, env=environment)
        return [tuple([parts[0], *map(int, parts[1:])])
                for parts in (line.split() for line in result.stdout.splitlines())]

    @staticmethod
    def write(address, value, position=9, mask=0xffff):
        return f"W {position} {(address - 0xc00000) // 2} {value} {mask}"

    def compare_reference(self, reference):
        self.assertEqual(reference["schema"], 1)
        self.assertEqual(reference["source"]["handler_file_offset"], 0xb2ca8)
        self.assertTrue(reference["cases"])
        for case in reference["cases"]:
            inputs, output = case["input"], case["output"]
            address, value = inputs["byte_address"], inputs["data"]
            with self.subTest(address=hex(address), value=value):
                actual = self.run_commands([self.write(address, value), "R 10"])
                if output["direct_cram"]:
                    expected = [("C", item["index"], item["value"]) for item in output["cram_writes"]]
                else:
                    expected = [("P", ((address - 0xc00000) // 2) & 0x0f, value, 0xffff)]
                self.assertEqual(actual, expected)

    def test_matches_original_arm_address_decoder(self):
        self.compare_reference(json.loads(FIXTURE.read_text()))

    def test_matches_fresh_original_arm_run_when_configured(self):
        path = os.environ.get("MDP_CRAM_ORACLE_JSON")
        if not path:
            self.skipTest("MDP_CRAM_ORACLE_JSON is not configured")
        self.compare_reference(json.loads(Path(path).read_text()))

    def test_all_128_entries_survive_same_scanline_and_flush_only_once(self):
        commands = [self.write(0xc00400 + index * 2, 17 + index * 93) for index in range(128)]
        commands += ["R 10", "R 10", "R 11"]
        self.assertEqual(self.run_commands(commands), [("C", index, 17 + index * 93) for index in range(128)])

    def test_last_write_wins_only_for_its_own_entry(self):
        self.assertEqual(self.run_commands([
            self.write(0xc00400, 0x222), self.write(0xc00462, 0x468),
            self.write(0xc00462, 0xace), self.write(0xc004fe, 0xeee), "R 10",
        ]), [("C", 0, 0x222), ("C", 0x31, 0xace), ("C", 127, 0xeee)])

    def test_preserves_next_scanline_timing_and_invalid_render_bounds(self):
        self.assertEqual(self.run_commands([
            self.write(0xc00462, 0x468), "R -1", "R 224", "R 9", "R 10", "R 10",
        ]), [("C", 0x31, 0x468)])

    def test_last_visible_line_and_vblank_schedule_line_zero(self):
        for position in (223, 224, 261, -2, -1):
            with self.subTest(position=position):
                self.assertEqual(self.run_commands([
                    self.write(0xc00462, 0x468, position), "R 223", "R 0", "R 0",
                ]), [("C", 0x31, 0x468)])

    def test_soft_reset_discards_all_pending_lines_and_entries(self):
        self.assertEqual(self.run_commands([
            self.write(0xc00400, 0x222, 261), self.write(0xc00462, 0x468, 99),
            self.write(0xc004fe, 0xace, 99), "Z", "R 0", "R 100",
            self.write(0xc00462, 0xeee, 99), "R 100",
        ]), [("C", 0x31, 0xeee)])

    def test_ordinary_ports_preserve_data_and_byte_enable_mask(self):
        self.assertEqual(self.run_commands([
            self.write(0xc00004, 0x1234, mask=0xff00),
            self.write(0xc00662, 0xabcd, mask=0x00ff), "R 10",
        ]), [("P", 2, 0x1234, 0xff00), ("P", 1, 0xabcd, 0x00ff)])


if __name__ == "__main__":
    unittest.main()
