import hashlib
import importlib.util
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "rompatch" / "patch.py"
GENERATOR = ROOT / "scripts" / "generate_rom_patch_header.py"
MAME_PATCH = ROOT / "patches" / "mame0289-space-harrier-mdp.patch"

ROMS = {
    "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72": {
        "file": "jp_jp_space_harrier.smp",
        "size": 0x3E0000,
        "patched": "718c21dc6e71e6a408bc35ebbe8ea755f3ad69e3",
        "words": 119,
        "total": 129,
    },
    "80f576af01d6413c0b92073e2f947b0431f12a74": {
        "file": "jp_jp_Space_Harrier_II.smp",
        "size": 0x380000,
        "patched": "f40ff2894c1c7eee0bbae65643670fcb084a287e",
        "words": 119,
        "total": 121,
    },
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RomPatchTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = load_module(PATCHER, "sh_mdp_patch_test")

    def test_supported_rom_manifest_is_complete(self):
        self.assertEqual(set(self.patch.ROMS), set(ROMS))
        for sha1, expected in ROMS.items():
            name, words = self.patch.ROMS[sha1]
            self.assertTrue(name.startswith("Space Harrier"))
            self.assertEqual(len(words), expected["words"])
            total = len(words) + len(self.patch.EXTRA_PATCHES.get(sha1, ()))
            self.assertEqual(total, expected["total"])

    def test_patch_ranges_do_not_overlap_or_escape_rom(self):
        for sha1, (_name, words) in self.patch.ROMS.items():
            occupied = set()
            size = ROMS[sha1]["size"]
            for offset, bad, good, *_ in words:
                self.assertNotEqual(bad, good)
                self.assertGreaterEqual(offset, 0)
                self.assertLess(offset + 1, size)
                self.assertFalse({offset, offset + 1} & occupied)
                occupied.update((offset, offset + 1))
            for offset, before, after, _description in self.patch.EXTRA_PATCHES.get(sha1, ()):
                self.assertEqual(len(before), len(after))
                self.assertLessEqual(offset + len(after), size)
                self.assertFalse(set(range(offset, offset + len(after))) & occupied)
                occupied.update(range(offset, offset + len(after)))

    def test_generated_adapter_contains_both_roms(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "sh1_mdp_rom.h"
            subprocess.run(
                ["python3", str(GENERATOR), str(PATCHER), str(header)],
                check=True,
            )
            text = header.read_text(encoding="utf-8")
        for sha1, expected in ROMS.items():
            self.assertIn(sha1, text)
            self.assertIn(f"size == 0x{expected['size']:x}", text)

    def test_sh2_controller_reader_loads_the_port_address(self):
        """Protect the opcode whose corruption made every SH2 control inert."""
        sh2_words = self.patch.ROMS["80f576af01d6413c0b92073e2f947b0431f12a74"][1]
        entry = next(item for item in sh2_words if item[0] == 0x1972D6)
        self.assertEqual(entry[1], 0x0100)
        self.assertEqual(entry[2], 0x206F)  # movea.l $4(a7),a0

    def test_mdp_extended_cram_does_not_wrap_over_sprite_palettes(self):
        """Protect SH2 gameplay palettes from the 0x40..0xbe bulk clear."""
        text = MAME_PATCH.read_text(encoding="utf-8")
        self.assertIn("std::make_unique<u16[]>(0x100 / 2)", text)
        self.assertIn("memset(m_cram.get(), 0x00, 0x100)", text)
        self.assertIn("save_pointer(NAME(m_cram), 0x100 / 2)", text)
        self.assertGreaterEqual(
            text.count("(m_vdp_address & 0xfe) >> 1"),
            3,
        )
        self.assertIn("m_use_cram && offset < 0x40", text)

    def test_sh2_ceiling_is_kept_above_the_open_stage_scenery(self):
        """Protect Yees Land's ceiling without restoring doubled mountains."""
        text = MAME_PATCH.read_text(encoding="utf-8")
        self.assertIn("constexpr int top_bias = 53", text)
        self.assertIn("table_line < 112 && srcy >= 336", text)
        self.assertIn("224 - perspective", text)
        self.assertIn("if (sh2_layout && srcy >= 432)", text)

    def test_mdp_palette_uses_the_linear_mark_v_dac(self):
        """Protect the Mini 2 colour ramp instead of the nonlinear MD DAC."""
        text = MAME_PATCH.read_text(encoding="utf-8")
        self.assertIn("static rgb_t mdp_palette_pen", text)
        self.assertIn("return c * 32", text)
        self.assertGreaterEqual(text.count("mdp_palette_pen("), 7)

    def test_sh2_text_and_boss_fonts_keep_distinct_banks(self):
        """Menus/scores use 4xx; coloured boss names stay in 6xx."""
        text = MAME_PATCH.read_text(encoding="utf-8")
        self.assertIn("tile.colour == 2 && code >= 0x6a0", text)
        sh2_extra = self.patch.EXTRA_PATCHES[
            "80f576af01d6413c0b92073e2f947b0431f12a74"
        ]
        self.assertNotIn(0x1ACF96, {entry[0] for entry in sh2_extra})
        self.assertNotIn(0x1ACFA6, {entry[0] for entry in sh2_extra})


class PrivateRomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("SH_MDP_ROM_DIR")
        if not value:
            raise unittest.SkipTest("SH_MDP_ROM_DIR is not configured")
        cls.rom_dir = Path(value)

    def test_pristine_and_patched_hashes(self):
        for original_sha1, expected in ROMS.items():
            source = self.rom_dir / expected["file"]
            self.assertTrue(source.is_file(), f"missing private ROM: {source}")
            self.assertEqual(source.stat().st_size, expected["size"])
            self.assertEqual(hashlib.sha1(source.read_bytes()).hexdigest(), original_sha1)
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "patched.md"
                subprocess.run(
                    ["python3", str(PATCHER), str(source), str(output)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
                self.assertEqual(hashlib.sha1(output.read_bytes()).hexdigest(), expected["patched"])

    def test_every_pristine_word_matches_the_table(self):
        patch = load_module(PATCHER, "sh_mdp_patch_private_test")
        for sha1, expected in ROMS.items():
            data = (self.rom_dir / expected["file"]).read_bytes()
            for offset, bad, _good, mnemonic, _source in patch.ROMS[sha1][1]:
                actual = struct.unpack_from(">H", data, offset)[0]
                self.assertEqual(actual, bad, f"{sha1} {offset:06x}: {mnemonic}")

    def test_every_pristine_extra_patch_matches(self):
        patch = load_module(PATCHER, "sh_mdp_patch_extra_private_test")
        for sha1, expected in ROMS.items():
            data = (self.rom_dir / expected["file"]).read_bytes()
            for offset, before, _after, description in patch.EXTRA_PATCHES.get(sha1, ()):
                self.assertEqual(
                    data[offset:offset + len(before)], before,
                    f"{sha1} {offset:06x}: {description}",
                )


if __name__ == "__main__":
    unittest.main()
