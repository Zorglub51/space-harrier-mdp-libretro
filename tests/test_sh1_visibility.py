"""Keep SH1's structural and player hides while removing depth thinning."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Sh1Visibility(unittest.TestCase):
    def test_depth_thinning_preserves_shadow_flag_and_object_lifecycle(self):
        code = r'''
#include "sh1_visibility.h"
#include <array>
#include <cassert>
#include <cstdint>
using sh1_markvi_visibility::normalize_flags;
int main()
{
    constexpr std::array<std::uint32_t, 6> body_handlers{{
        0x1246c8, 0x1247f0, 0x124ae4, 0x124e20, 0x12510e, 0x1e41d8
    }};
    for (const auto routine : body_handlers) {
        // Every other flag survives, including collision/scale and shadow bits.
        // Exercise all flag words rather than only an isolated 0x80 example.
        for (unsigned flags = 0; flags <= 0xffff; ++flags) {
            const auto normalized = normalize_flags(routine, 0xfd, flags);
            assert((normalized ^ flags) == (flags & 0x80));
            assert((normalized & 4) == (flags & 4));
            assert(normalize_flags(routine, 0xfe, flags) == flags);
            assert(normalize_flags(routine, 0xff, flags) == flags);
        }
        const std::uint16_t guest_flags = 0x1280;
        assert((normalize_flags(routine, 0, guest_flags) & 0x80) == 0);
        assert((normalize_flags(routine, 0, guest_flags) & 0x84) == 0);
        assert((normalize_flags(routine, 0, guest_flags | 4) & 0x84) == 4);
        assert(guest_flags == 0x1280);    // No guest/snapshot mutation.
    }
    // Same object slot, different lifecycle: retiring/destroyed bodies remain
    // hidden. Spatially coincident pieces use pose FF, not depth-thinning.
    for (const auto routine : {0x12df10u, 0x1e4e9au, 0x1e4fbcu, 0x1e30f8u}) {
        assert(normalize_flags(routine, 0, 0x80) == 0x80);
        assert(normalize_flags(routine, 0xff, 0) == 0);
    }
    // Harrier's actual blinking handlers and ordinary unknown objects retain
    // their native visibility, even if their slot once held a thinned segment.
    for (const auto routine : {0x1dd4e0u, 0x1dd698u, 0u, 0x1246cau,
                               0x1e41dau, 0x101e41d8u})
        assert(normalize_flags(routine, 0, 0xa5ff) == 0xa5ff);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "visibility.cpp"
            binary = Path(temp) / ("visibility.exe" if os.name == "nt" else "visibility")
            source.write_text(code)
            subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
                "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                "-I", str(ROOT / "src/markv"), str(source), "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
