"""Compile the production adapter; private artwork checks require SH_MDP_ROM_DIR.

No donor code, artwork or palette payload is distributed by this test. The
optional checks read the user's authenticated ROMs and keep generated images
inside a TemporaryDirectory.
"""
import hashlib
import json
import os
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "src/markv/sh2_explosion_patch.h"
ROM_INFO = {
    "sh1": ("jp_jp_space_harrier.smp", "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72"),
    "sh2": ("jp_jp_Space_Harrier_II.smp", "80f576af01d6413c0b92073e2f947b0431f12a74"),
}
CLOCK_SITES = (0x09d8b0, 0x09ec9e, 0x09ee8c, 0x09f2d2, 0x09f2ec,
               0x165d86, 0x175f86, 0x177264, 0x178f3c, 0x18f060, 0x18f654)
PARTICLE_SITES = (0x18fc88, 0x18fe36)
TRACKED_SITES = (0x0cba62, 0x0cbc24, 0x137c88, 0x158d9a, 0x164910,
                 0x16d53c, 0x16d8bc, 0x16deca, 0x17328c, 0x173b26,
                 0x173dc6, 0x18bb30, 0x194ef4, 0x19550c, 0x1956a2)


def word(data, offset):
    return struct.unpack_from(">H", data, offset)[0]


def longword(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


PROBE = r'''
#include "sh2_explosion_patch.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>

using bytes = std::vector<std::uint8_t>;
bytes read(const char *name) {
    std::ifstream file(name, std::ios::binary);
    if (!file) throw std::runtime_error("missing input");
    return bytes(std::istreambuf_iterator<char>(file), {});
}
int main(int argc, char **argv) {
    if (argc == 2 && std::string(argv[1]) == "classifier") {
        bool comma = false; std::cout << '[';
        for (const auto &entry : markv::sh2_explosion_detail::enemy_spawns) {
            if (comma) std::cout << ',';
            comma = true;
            std::cout << '[' << entry.site << ',' << entry.method << ','
                      << entry.descriptor << ',' << entry.reaction_clear << ']';
        }
        std::cout << "]\n"; return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "guards") {
        bytes rom(0x400000, 0), donor(0x3e0000, 0);
        auto apply = [&](std::uint8_t *r, std::size_t n,
                         const std::uint8_t *d, std::size_t z) {
            return markv::apply_sh2_enemy_explosions(r, n, d, z);
        };
        const bool null_rom = !apply(nullptr, rom.size(), donor.data(), donor.size());
        const bool null_donor = !apply(rom.data(), rom.size(), nullptr, donor.size());
        const bool capacity = !apply(rom.data(), 0x3fffff, donor.data(), donor.size());
        const bool donor_size = !apply(rom.data(), rom.size(), donor.data(), 0x3dffff);
        const bool signature = !apply(rom.data(), rom.size(), donor.data(), donor.size());
        const bool unchanged = std::all_of(rom.begin(), rom.end(), [](auto v) { return !v; });
        std::cout << "{\"null_rom\":" << null_rom << ",\"null_donor\":" << null_donor
                  << ",\"capacity\":" << capacity << ",\"donor_size\":" << donor_size
                  << ",\"signature\":" << signature << ",\"unchanged\":" << unchanged << "}\n";
        return 0;
    }
    if (argc != 5 || std::string(argv[1]) != "apply") return 2;
    auto donor = read(argv[2]); auto rom = read(argv[3]);
    rom.resize(0x400000, 0xff);
    const bool ok = markv::apply_sh2_enemy_explosions(rom.data(), rom.size(), donor.data(), donor.size());
    std::ofstream output(argv[4], std::ios::binary);
    output.write(reinterpret_cast<const char *>(rom.data()), rom.size());
    std::cout << "{\"ok\":" << ok << "}\n";
    return 0;
}
'''


class CompiledProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CXX") or shutil.which("c++")
        if not compiler:
            raise unittest.SkipTest("a C++ compiler is required")
        cls.tmp = tempfile.TemporaryDirectory(prefix="sh2-explosion-test-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.work = Path(cls.tmp.name)
        source = cls.work / "probe.cpp"
        source.write_text(PROBE, encoding="utf-8")
        cls.probe = cls.work / ("probe.exe" if os.name == "nt" else "probe")
        compiled = subprocess.run(
            shlex.split(compiler) + ["-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror",
             "-I", str(HEADER.parent), str(source), "-o", str(cls.probe)],
            capture_output=True, text=True,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def run_probe(self, *arguments):
        result = subprocess.run(
            [str(self.probe), *map(str, arguments)], check=True,
            capture_output=True, text=True,
        )
        return json.loads(result.stdout)


class ExplosionAdapterGuards(CompiledProbe):
    def test_invalid_pointers_sizes_and_signatures_reject_without_writes(self):
        checks = self.run_probe("guards")
        self.assertEqual(len(checks), 6)
        self.assertTrue(all(checks.values()), checks)


class PrivateExplosionPayloadTests(CompiledProbe):
    @classmethod
    def setUpClass(cls):
        location = os.environ.get("SH_MDP_ROM_DIR")
        if not location:
            raise unittest.SkipTest("SH_MDP_ROM_DIR is not configured")
        super().setUpClass()
        cls.rom_dir = Path(location)
        cls.inputs = {}
        for game, (filename, digest) in ROM_INFO.items():
            path = cls.rom_dir / filename
            data = path.read_bytes()
            if hashlib.sha1(data).hexdigest() != digest:
                raise AssertionError(f"unsupported {game} donor SHA-1")
            cls.inputs[game] = data
        cls.base_path = cls.work / "baseline.md"
        subprocess.run(
            ["python3", str(ROOT / "rompatch/patch.py"),
             str(cls.rom_dir / ROM_INFO["sh2"][0]), str(cls.base_path)],
            check=True, capture_output=True, text=True,
        )
        cls.base = cls.base_path.read_bytes()
        cls.output_path = cls.work / "optional.md"
        result = subprocess.run(
            [str(cls.probe), "apply", str(cls.rom_dir / ROM_INFO["sh1"][0]),
             str(cls.base_path), str(cls.output_path)],
            check=True, capture_output=True, text=True,
        )
        if not json.loads(result.stdout)["ok"]:
            raise AssertionError("production adapter rejected authenticated ROMs")
        cls.output = cls.output_path.read_bytes()

    def test_all_44_donor_payloads_and_piece_geometry_are_preserved(self):
        donor = self.inputs["sh1"]
        pixel_ranges, piece_ranges = [], []
        for pose in range(11):
            for lod, expected_count in enumerate((4, 30, 80, 154)):
                with self.subTest(pose=pose + 1, lod=lod):
                    old = 0xd84 + pose * 88 + lod * 22
                    new = 0x382000 + pose * 88 + lod * 22
                    self.assertEqual(self.output[new + 4:new + 8], donor[old + 4:old + 8])
                    self.assertEqual(self.output[new + 10:new + 12], donor[old + 10:old + 12])
                    self.assertEqual(self.output[new + 16:new + 22], donor[old + 16:old + 22])
                    self.assertEqual(word(self.output, new + 4), expected_count)
                    self.assertEqual(word(self.output, new + 8), 0x180 + lod)
                    source, dest = longword(donor, old), longword(self.output, new)
                    size = expected_count * 32
                    self.assertEqual(self.output[dest:dest + size], donor[source:source + size])
                    pixel_ranges.append((dest, dest + size))
                    source_parts = longword(donor, old + 12)
                    dest_parts = longword(self.output, new + 12)
                    n = donor[old + 10]
                    piece_ranges.append((dest_parts, dest_parts + n * 12))
                    for index in range(n):
                        a, b = source_parts + index * 12, dest_parts + index * 12
                        self.assertEqual(word(self.output, b), word(donor, a) | 0x40)
                        self.assertEqual(self.output[b + 2:b + 12], donor[a + 2:a + 12])
        self.assertEqual(sum(end - begin for begin, end in pixel_ranges), 94336)
        for ranges, lower, upper in ((pixel_ranges, 0x384000, 0x39c000),
                                     (piece_ranges, 0x382400, 0x384000)):
            self.assertEqual(ranges[0][0], lower)
            self.assertLessEqual(ranges[-1][1], upper)
            self.assertTrue(all(a[1] == b[0] for a, b in zip(ranges, ranges[1:])))
        self.assertEqual(self.output[0x39c000:0x39c020], donor[0x393aea:0x393b0a])

    def test_original_sh2_explosion_art_and_descriptors_are_unchanged(self):
        for first, end in ((0x744, 0x7b2), (0x78d88, 0x79f08), (0x86ec8, 0x877c8)):
            self.assertEqual(self.output[first:end], self.base[first:end])
        for record in range(0x744, 0x7b2, 22):
            parts = longword(self.base, record + 12)
            size = self.base[record + 10] * 12
            self.assertEqual(self.output[parts:parts + size], self.base[parts:parts + size])

    def test_native_motion_and_cleanup_run_before_visual_wrappers(self):
        # All three original handlers, including their free-list writes and
        # the tracked-death counter decrement, must remain byte-identical.
        for start, end in ((0x137afc, 0x137c78), (0x137cf0, 0x137f0a),
                           (0x137f0a, 0x13811e)):
            self.assertEqual(self.output[start:end], self.base[start:end])
        for wrapper, native in ((0x380300, 0x137f0a), (0x380400, 0x137afc),
                                (0x380500, 0x137cf0), (0x380c00, 0x137afc),
                                (0x380d00, 0x137cf0)):
            with self.subTest(wrapper=f"{wrapper:06x}"):
                # Save preserved registers and the old descriptor, then invoke
                # the original handler before any visual mutation. Returning
                # a freed object (state FF) must branch directly to the epilogue.
                prefix = (bytes.fromhex("48e73020246f0010242a001c2f0a4eb9") +
                          struct.pack(">I", native) +
                          bytes.fromhex("588f0c2a00ff00206700"))
                self.assertEqual(self.output[wrapper:wrapper + len(prefix)], prefix)
                displacement = struct.unpack_from(">h", self.output, wrapper + len(prefix))[0]
                target = wrapper + len(prefix) + displacement
                self.assertEqual(self.output[target:target + 6], bytes.fromhex("4cdf040c4e75"))

    def test_hostile_actor_and_boss_particle_sites_only_change_the_method(self):
        for sites, native, wrapper in ((PARTICLE_SITES, 0x137afc, 0x380c00),
                                       (TRACKED_SITES, 0x137cf0, 0x380d00)):
            for site in sites:
                with self.subTest(site=f"{site:06x}"):
                    expected = bytes.fromhex("217c") + struct.pack(">I", native) + bytes.fromhex("0010")
                    self.assertEqual(self.base[site:site + 8], expected)
                    expected = bytes.fromhex("217c") + struct.pack(">I", wrapper) + bytes.fromhex("0010")
                    self.assertEqual(self.output[site:site + 8], expected)

    def test_classifier_matches_actor_factory_signatures_and_excludes_scenery(self):
        entries = self.run_probe("classifier")
        self.assertEqual(len(entries), 51)
        methods = {entry[1] for entry in entries}
        self.assertEqual(len(methods), 50)
        self.assertTrue({0x0dcb7e, 0x0d85c4, 0x0d6baa, 0x0e52d0, 0x14393a} <= methods)
        self.assertTrue({0x0f14a2, 0x0f15e8, 0x174f7e, 0x190900}.isdisjoint(methods))
        for index, (site, method, descriptor, reaction_clear) in enumerate(entries):
            with self.subTest(site=f"{site:06x}"):
                self.assertEqual(word(self.base, site), 0x4879)
                self.assertEqual(longword(self.base, site + 2), method)
                self.assertEqual(word(self.base, site + 6), 0x4879)
                self.assertEqual(longword(self.base, site + 8), descriptor)
                self.assertEqual(word(self.base, site + 12), 0x4eb9)
                self.assertEqual(longword(self.base, site + 14), 0x13d6b4)
                self.assertEqual(self.base[reaction_clear:reaction_clear + 4],
                                 bytes.fromhex("42280023"))
                self.assertEqual(longword(self.output, 0x380900 + index * 4), method)

    def test_original_rom_changes_are_confined_to_validated_guest_operands(self):
        allowed = bytearray(len(self.base))
        hook_ranges = ([(0x139b84, 0x139b8c)] + [(site, site + 6) for site in CLOCK_SITES] +
                       [(site + 2, site + 6) for site in PARTICLE_SITES + TRACKED_SITES])
        for first, end in hook_ranges:
            allowed[first:end] = b"\1" * (end - first)
        references = 0
        for offset in range(2, len(self.base) - 3, 2):
            if longword(self.base, offset) == 0xff3542:
                references += 1
                self.assertIn(word(self.base, offset - 2) & 0xf1ff, (0x41f9, 0x203c))
                allowed[offset:offset + 4] = b"\1" * 4
                self.assertEqual(longword(self.output, offset), 0xfe0100)
        self.assertEqual(references, 190)
        unexpected = [i for i, (a, b) in enumerate(zip(self.base, self.output))
                      if a != b and not allowed[i]]
        self.assertEqual(unexpected[:10], [])
        self.assertEqual(len(self.output), 0x400000)
        self.assertEqual(self.output[0x39c020:], b"\xff" * (0x400000 - 0x39c020))
        self.assertEqual(word(self.output, 0x139b84), 0x4ef9)
        self.assertEqual(longword(self.output, 0x139b86), 0x380100)
        for offset in CLOCK_SITES:
            self.assertEqual(self.base[offset:offset + 6], bytes.fromhex("52b900ff387e"))
            self.assertEqual(word(self.output, offset), 0x4eb9)
            self.assertEqual(longword(self.output, offset + 2), 0x380800)

    def test_modified_real_signatures_and_out_of_bounds_donor_records_reject(self):
        # Unlike a blank-buffer guard, these inputs pass all other authentication
        # prerequisites of the production builder up to the damaged field.
        cases = (("constructor", "sh2", 0x139b84, b"\0\0"),
                 ("tick", "sh2", 0x09d8b0, b"\0\0"),
                 ("actor_factory_pea", "sh2", 0x0a4b48, b"\0\0"),
                 ("actor_factory_target", "sh2", 0x0a4b56, b"\0\0\0\0"),
                 ("actor_reaction", "sh2", 0x0a4b68, b"\0\0"),
                 ("last_actor_factory", "sh2", 0x0a5ade, b"\0\0"),
                 ("boss_particle_method", "sh2", 0x18fc8a, b"\0\0\0\0"),
                 ("tracked_death_method", "sh2", 0x1956a4, b"\0\0\0\0"),
                 ("donor_entry", "sh1", 0x1d7404, b"\0\0"),
                 ("pixel_pointer_wrap", "sh1", 0xd84, b"\xff\xff\xff\xf0"),
                 ("piece_pointer_wrap", "sh1", 0xd90, b"\xff\xff\xff\xf0"))
        for name, game, offset, replacement in cases:
            with self.subTest(name=name):
                donor = bytearray(self.inputs["sh1"])
                rom = bytearray(self.base)
                damaged = donor if game == "sh1" else rom
                damaged[offset:offset + len(replacement)] = replacement
                donor_path, rom_path = self.work / "bad-sh1.md", self.work / "bad-sh2.md"
                donor_path.write_bytes(donor)
                rom_path.write_bytes(rom)
                output = self.work / "rejected.md"
                self.assertFalse(self.run_probe("apply", donor_path, rom_path, output)["ok"])
                self.assertEqual(output.read_bytes(), bytes(rom) + b"\xff" * (0x400000 - len(rom)))


if __name__ == "__main__":
    unittest.main()
