"""Exercise the shipped direct VRAM accessors and glyph-cache invalidation."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments


class DirectVramTests(unittest.TestCase):
    def test_font_writes_reach_vram_and_invalidate_all_glyph_caches(self):
        patch = PATCH.read_text()
        header = patched_fragments(patch, "src/devices/video/315_5313.h")
        mapping = patched_fragments(patch, "src/mame/sega/megadriv.cpp")
        self.assertIn("map(0xd00000, 0xd0ffff).rw(m_vdp, FUNC(sega315_5313_device::vram_direct_r), FUNC(sega315_5313_device::vram_direct_w))", mapping)
        self.assertIn("map(0xd10000, 0xd1ffff).rw(m_vdp, FUNC(sega315_5313_device::mdp_gfx_r), FUNC(sega315_5313_device::mdp_gfx_w))", mapping)
        methods = "\n".join(full_function(header, signature) for signature in (
            "u16 vram_direct_r(", "void vram_direct_w(", "void vram_w("))
        # Default arguments are MAME's ~0 convention; give the standalone
        # probe the equivalent u16 value without a conversion warning.
        methods = methods.replace("= ~0", "= 0xffff")
        source = r'''
#include <array>
#include <cassert>
#include <cstdint>
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using offs_t = std::uint32_t;
#define COMBINE_DATA(pointer) (*(pointer) = (*(pointer) & ~mem_mask) | (data & mem_mask))
#define MEGADRIV_VDP_VRAM(offset) m_vram[offset]
struct gfx_element {
    unsigned dirty_calls = 0, last_dirty = 0, last_code = 0;
    std::array<u8, 64> pixels{};
    void mark_dirty(unsigned code) { ++dirty_calls; last_dirty = code; }
    unsigned height() const { return 8; }
    unsigned rowbytes() const { return 8; }
    unsigned elements() const { return 2048; }
    const u8 *get_data(unsigned code) { last_code = code; return pixels.data(); }
};
class sega315_5313_device {
public:
    u16 m_regs[64]{};
    bool m_markvi_ready[3]{};
    std::array<u16, 32768> m_vram{};
    std::array<gfx_element, 6> graphics{};
    gfx_element *gfx(unsigned index) { return &graphics[index]; }
    METHODS
};
int main() {
    sega315_5313_device vdp;
    vdp.m_regs[5] = 0x70;
    vdp.m_markvi_ready[2] = true;
    vdp.vram_direct_w(0x7000, 0);
    assert(!vdp.m_markvi_ready[2]);
    for (auto &g : vdp.graphics) g.dirty_calls = 0;
    const unsigned font_word = (0xd0d400 - 0xd00000) / 2;
    vdp.vram_direct_w(font_word, 0x1234);
    assert(vdp.vram_direct_r(font_word) == 0x1234);
    assert(vdp.m_vram[0x6a0 * 16] == 0x1234);
    for (unsigned i = 0; i < 6; ++i) {
        assert(vdp.graphics[i].dirty_calls == 1);
        assert(vdp.graphics[i].last_dirty == (i % 2 ? 0x350 : 0x6a0));
    }
    vdp.vram_direct_w(font_word, 0xab00, 0xff00);
    assert(vdp.vram_direct_r(font_word) == 0xab34);
    vdp.vram_direct_w(font_word, 0x00cd, 0x00ff);
    assert(vdp.vram_direct_r(font_word) == 0xabcd);
    vdp.vram_direct_w(0x7fff, 0xface);
    assert(vdp.vram_direct_r(0x7fff) == 0xface);
}
'''.replace("METHODS", methods)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            program = directory / "probe.cpp"
            program.write_text(source)
            binary = directory / ("probe.exe" if os.name == "nt" else "probe")
            compiler = shlex.split(os.environ.get("CXX", "c++"))
            subprocess.run(compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
                                       str(program), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
