"""Compare SH2's reconstructed tilemap block with original ARM observations.

The fixture contains synthetic state and bus observations, without game assets
or original executable code. The C++ reference is not an installed CPU hook.
"""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sh2_tilemap_m2.json"

PROBE = r'''
#include "markv/sh2_tilemap_hook.h"
#include <iostream>
#include <vector>
struct Bus {
    struct Access { bool write; std::uint32_t address; std::uint16_t value; };
    std::uint16_t source;
    std::vector<Access> accesses;
    std::uint16_t read_word(std::uint32_t address) {
        accesses.push_back({false, address, source});
        return source;
    }
    void write_word(std::uint32_t address, std::uint16_t value) {
        accesses.push_back({true, address, value});
    }
};
int main() {
    markv::CpuState cpu;
    for (unsigned i = 0; i != 8; ++i) {
        cpu.d[i] = 0xabc00000u + i;
        cpu.a[i] = 0xdef00000u + i;
    }
    std::uint32_t source, flags, extend, ticks;
    if (!(std::cin >> cpu.d[0] >> cpu.d[1] >> cpu.d[6] >> cpu.a[0] >> cpu.a[1]
          >> source >> flags >> extend >> ticks) || source > 65535 || flags > 255 || extend > 255)
        return 2;
    cpu.nzvc = std::uint8_t(flags);
    cpu.extend = std::uint8_t(extend);
    const auto before = cpu;
    Bus bus{std::uint16_t(source), {}};
    const auto exit = markv::sh2_tilemap_copy_word(cpu, bus, ticks);
    bool unchanged = true;
    for (unsigned i = 0; i != 8; ++i) {
        if (i != 6) unchanged &= cpu.d[i] == before.d[i];
        if (i != 0 && i != 1) unchanged &= cpu.a[i] == before.a[i];
    }
    std::cout << "{\"d0\":" << cpu.d[0] << ",\"d1\":" << cpu.d[1]
        << ",\"d6\":" << cpu.d[6] << ",\"a0\":" << cpu.a[0] << ",\"a1\":" << cpu.a[1]
        << ",\"flags\":" << unsigned(cpu.nzvc) << ",\"x\":" << unsigned(cpu.extend)
        << ",\"next_pc\":" << exit.next_pc << ",\"ticks\":" << exit.dispatch_counter
        << ",\"accesses\":[";
    for (std::size_t i = 0; i < bus.accesses.size(); ++i) {
        const auto &a = bus.accesses[i];
        if (i) std::cout << ',';
        std::cout << "{\"kind\":\"" << (a.write ? "write16" : "read16")
            << "\",\"address\":" << a.address << ",\"value\":" << a.value << '}';
    }
    std::cout << "],\"unrelated_registers_preserved\":" << (unchanged ? "true" : "false") << "}\n";
}
'''


class Sh2TilemapHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory / "probe.cpp"
        source.write_text(PROBE, encoding="utf-8")
        cls.probe = directory / ("probe.exe" if os.name == "nt" else "probe")
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        subprocess.run(compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                                  "-I", str(ROOT / "src"), str(source), "-o", str(cls.probe)], check=True)

    def compare_reference(self, reference):
        self.assertEqual(reference["schema"], 1)
        self.assertEqual(reference["source"]["guest_hook_pc"], 0x190A80)
        self.assertEqual(reference["source"]["handler_file_offset"], 0xBE9AC)
        self.assertGreaterEqual(len(reference["cases"]), 76)
        for case in reference["cases"]:
            with self.subTest(case=case["name"]):
                inputs = case["input"]
                values = [inputs[key] for key in (
                    "d0", "d1", "d6", "a0", "a1", "source_word", "flags", "x", "ticks")]
                result = subprocess.run([str(self.probe)], input=" ".join(map(str, values)) + "\n",
                                        capture_output=True, text=True, check=True)
                actual = json.loads(result.stdout)
                self.assertEqual({key: actual[key] for key in case["output"]}, case["output"])
                self.assertTrue(actual["unrelated_registers_preserved"])
                # A read from the source precedes exactly one destination write.
                accesses = actual["accesses"]
                self.assertEqual([entry["kind"] for entry in accesses], ["read16", "write16"])
                self.assertEqual(accesses[0]["address"], inputs["a0"] & 0xFFFFFF)
                self.assertEqual(accesses[1]["address"], inputs["a1"])
                self.assertLessEqual(set(case["changed_state_byte_offsets"]),
                                     {0x1E, 0x1F, 0x40, 0x41, *range(0x48, 0x50)})

    def test_matches_original_arm_reference(self):
        self.compare_reference(json.loads(FIXTURE.read_text(encoding="utf-8")))
        path = os.environ.get("SH2_TILEMAP_ORACLE_JSON")
        if path:
            self.compare_reference(json.loads(Path(path).read_text(encoding="utf-8")))

    def test_fixture_distinguishes_old_opcode_and_covers_loop_boundaries(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertEqual({case["output"]["next_pc"] for case in cases}, {0x190A80, 0x190A8A})
        self.assertTrue(any(case["output"]["x"] & 2 for case in cases))  # ADD overflow
        self.assertTrue(any(case["output"]["x"] & 1 for case in cases))  # ADD carry
        self.assertTrue(any(case["output"]["a0"] == 0 for case in cases))
        # The old opcode leaves D6 untouched before the ADD, accumulating the
        # base instead of loading each source index. Native outputs reject it.
        self.assertTrue(any(((case["input"]["d6"] + case["input"]["d1"]) & 65535)
                            != (case["output"]["d6"] & 65535) for case in cases))

    def test_rom_reconstruction_reads_source_into_d6(self):
        spec = importlib.util.spec_from_file_location("tilemap_rompatch", ROOT / "rompatch" / "patch.py")
        patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patch)
        entries = [entry for entry in patch.SH2 if entry[0] == 0x190A80]
        self.assertEqual([(entry[1], entry[2]) for entry in entries], [(0x2F3C, 0x3C18)])
        # Native results depend on the source word, not on the previous D6 value.
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertTrue(any((case["input"]["d6"] & 65535) != case["input"]["source_word"]
                            for case in cases))
        self.assertTrue(any(case["output"]["d6"] & 0xFFFF0000 for case in cases))


if __name__ == "__main__":
    unittest.main()
