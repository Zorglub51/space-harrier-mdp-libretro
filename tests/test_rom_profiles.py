"""Exercise the generated ROM adapter's game compatibility profile.

The hash stub supplies an already-computed identity. These public tests require
no game ROM and do not test MAME's SHA-1 implementation or the rendered output.
"""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SH1 = "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72"
SH2 = "80f576af01d6413c0b92073e2f947b0431f12a74"
SH1_SIZE = 0x3E0000
SH2_SIZE = 0x380000
UNKNOWN = "0000000000000000000000000000000000000000"

HASH_STUB = r"""
#pragma once
#include <cstdint>
#include <string>

namespace util {
inline std::string controlled_sha1;
struct sha1_t {
    std::string as_string() const { return controlled_sha1; }
};
struct sha1_creator {
    static sha1_t simple(const std::uint8_t *, std::uint32_t) { return {}; }
};
}
"""

PROBE = r"""
#include "sh1_mdp_rom.h"
#include <iostream>
#include <vector>

int main()
{
    // Deliberately retain this output between calls, including rejected ROMs.
    bool sh2_text_compat = true;
    std::uint32_t size;
    std::string mode;
    while (std::cin >> util::controlled_sha1 >> size >> mode)
    {
        std::vector<std::uint8_t> rom(size, 0xa5);
        bool applied;
        if (mode == "legacy")
            applied = sh1_mdp_rom::apply(rom.data(), size);
        else if (mode == "null")
            applied = sh1_mdp_rom::apply(rom.data(), size, nullptr);
        else if (mode == "profile")
            applied = sh1_mdp_rom::apply(rom.data(), size, &sh2_text_compat);
        else
            return 2;
        const bool changed = std::any_of(rom.begin(), rom.end(),
            [](std::uint8_t byte) { return byte != 0xa5; });
        std::cout << applied << ' ' << sh2_text_compat << ' ' << changed << '\n';
    }
    return std::cin.eof() ? 0 : 3;
}
"""


class RomProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        temp = Path(cls.temp.name)
        (temp / "util").mkdir()
        (temp / "util" / "hashing.h").write_text(HASH_STUB, encoding="utf-8")
        source = temp / "rom_profile_probe.cpp"
        source.write_text(PROBE, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "generate_rom_patch_header.py"),
             str(ROOT / "rompatch" / "patch.py"), str(temp / "sh1_mdp_rom.h")],
            check=True,
        )
        cls.probe = temp / ("rom_profile_probe.exe" if os.name == "nt" else "rom_profile_probe")
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        subprocess.run(
            compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                        "-I", str(temp), str(source), "-o", str(cls.probe)],
            check=True,
        )

    def run_sequence(self, cases):
        result = subprocess.run(
            [str(self.probe)],
            input="".join(f"{sha1} {size} {mode}\n" for sha1, size, mode in cases),
            text=True, capture_output=True, check=True,
        )
        # Each result is (ROM accepted, SH2 compatibility enabled, ROM changed).
        return [tuple(map(int, line.split())) for line in result.stdout.splitlines()]

    def test_profile_tracks_recognized_game_across_calls(self):
        self.assertEqual(self.run_sequence([
            (SH2, SH2_SIZE, "profile"),
            (SH1, SH1_SIZE, "profile"),
            (SH2, SH2_SIZE, "profile"),
        ]), [(1, 1, 1), (1, 0, 1), (1, 1, 1)])

    def test_unknown_identity_clears_previous_sh2_profile_without_patch(self):
        self.assertEqual(self.run_sequence([
            (SH2, SH2_SIZE, "profile"),
            (UNKNOWN, SH2_SIZE, "profile"),
        ]), [(1, 1, 1), (0, 0, 0)])

    def test_known_identity_with_wrong_size_clears_profile_without_patch(self):
        for sha1, size in ((SH2, SH1_SIZE), (SH1, SH2_SIZE), (SH2, 0)):
            with self.subTest(sha1=sha1, size=size):
                self.assertEqual(self.run_sequence([
                    (SH2, SH2_SIZE, "profile"),
                    (sha1, size, "profile"),
                ]), [(1, 1, 1), (0, 0, 0)])

    def test_existing_two_argument_calls_remain_compatible(self):
        self.assertEqual(self.run_sequence([
            (SH1, SH1_SIZE, "legacy"),
            (SH2, SH2_SIZE, "legacy"),
            (UNKNOWN, SH2_SIZE, "legacy"),
        ]), [(1, 1, 1), (1, 1, 1), (0, 1, 0)])

    def test_explicit_null_output_is_safe(self):
        self.assertEqual(self.run_sequence([
            (SH1, SH1_SIZE, "null"),
            (SH2, SH2_SIZE, "null"),
            (UNKNOWN, SH2_SIZE, "null"),
        ]), [(1, 1, 1), (1, 1, 1), (0, 1, 0)])


if __name__ == "__main__":
    unittest.main()
