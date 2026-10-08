// license:GPL-2.0-or-later
#pragma once

#include <cstdint>

namespace sh1_markvi_visibility {

// The six SH1 routines whose native bit-0x80 writers only thin nearby body
// segments by index. This is deliberately narrower than ignoring every native
// hidden flag. The retiring handlers and Harrier are not in this set.
inline bool has_depth_thinning(std::uint32_t routine)
{
    switch (routine) {
    case 0x1246c8:
    case 0x1247f0:
    case 0x124ae4:
    case 0x124e20:
    case 0x12510e:
    case 0x1e41d8:
        return true;
    default:
        return false;
    }
}

// Use for a live object's body and shadow decisions. SH1 tests (flags & 0x84)
// for shadows: remove only the shared depth budget, retaining the independent
// shadow-hide bit 0x04.
// Keeping the already-written flag, rather than recomputing a depth predicate,
// preserves the native update order. No guest state or hidden pose is changed.
inline std::uint16_t normalize_flags(std::uint32_t routine, unsigned pose,
                                     std::uint16_t flags)
{
    if (pose <= 0xfd && has_depth_thinning(routine))
        return flags & std::uint16_t(0xff7f);
    return flags;
}

} // namespace sh1_markvi_visibility
