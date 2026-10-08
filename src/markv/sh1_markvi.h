// license:GPL-2.0-or-later
#pragma once

#include "sh2_markvi.h"
#include "sh1_visibility.h"

namespace sh1_markvi {

using sprite = sh2_markvi::sprite;

// Translation of SH1 1702EC..172504, before its 40/80-entry partitioning.
// SH1 uses a separate object chain, tile cache and depth/shadow tables.
// The native arithmetic and body-then-shadow ordering match its constructor.
// Read returns a big-endian guest word. It must read an emitter-entry snapshot,
// not live objects (the game can update those before the next SAT upload).
template<class Read> bool build(Read read, std::vector<sprite> &out, bool widescreen = false)
{
    using u16 = std::uint16_t;
    using u32 = std::uint32_t;
    auto word = [&](u32 p) -> u16 { return read(p & 0xfffffe); };
    auto byte = [&](u32 p) -> unsigned { return (word(p) >> ((p & 1) ? 0 : 8)) & 255; };
    auto lng = [&](u32 p) -> u32 { return (u32(word(p)) << 16) | word(p + 2); };
    auto signed16 = [](u16 x) -> int { return x < 0x8000 ? x : int(x) - 0x10000; };
    auto sw = [&](u32 p) -> int { return signed16(word(p)); };
    // Explicit arithmetic shifts, including negative half-pixel positions.
    auto floor_shift = [](std::int64_t x, unsigned n) -> int {
        return int(x >= 0 ? x >> n : -((-x + ((std::int64_t(1) << n) - 1)) >> n));
    };
    const u32 tile_table = 0xff3d16; // Native LEA at 1704FC (and every emission branch).
    out.clear();
    std::vector<u32> objects;
    std::unordered_set<u32> seen;
    for (u32 o = lng(0xff40b8) & 0xffffff; o; o = lng(o + 0x18) & 0xffffff) {
        // Structural validation, not an object or sprite quota.
        if ((o & 1) || o < 0xff0000 || o > 0xffffb4 || !seen.insert(o).second)
            return false;
        objects.push_back(o);
    }
    auto emit = [&](u32 o, u32 desc, unsigned flags, int scale, int x, int y, bool shadow) {
        const u16 alloc = word(tile_table + word(desc + 8) * 2);
        const u16 base = (alloc & 0x7ff) + (flags << 11) + (shadow ? 0x6000 : byte(o + 0x22) << 13);
        const u32 parts = lng(desc + 12);
        const unsigned count = byte(desc + 10);
        const bool mirror = (flags & 7) >= 4;
        for (unsigned half = 0; half < (mirror ? 2u : 1u); ++half) {
            // 170C64/170D4C (scaled), 171E9E/171F3C (unscaled): the
            // mirrored half has its own native flag mask, including Y flip.
            const unsigned half_flags = half ? ((flags << 11) & 0x1000) | 0x0800
                                             : ((flags << 11) & 0xc000);
            u16 attr = mirror ? u16(half_flags + (byte(o + 0x22) << 13) + (alloc & 0x7ff)) : base;
            // Native scaled emission memoizes horizontal coordinates from the
            // first row and reuses them in subsequent rows of the tile grid.
            // Store them dynamically rather than inheriting its stack capacity.
            std::vector<int> first_row_x;
            int last_dy = 0x7fff, row = -1;
            unsigned column = 0;
            for (unsigned i = 0; i < count; ++i) {
                const u32 p = parts + i * 12;
                int dx = sw(p + ((flags & 1) ? 8 : 4));
                int dy = sw(p + ((flags & 2) ? 10 : 6));
                if (mirror) {
                    dx = signed16(u16(sw(p + (half ? 8 : 4)) + (half ? -1 : 1) * int(byte(desc + 6)) * 4));
                    dy = sw(p + 6);
                }
                int projected_dx = dx;
                if (scale >= 0) {
                    if (dy != last_dy) { last_dy = dy; ++row; column = 0; }
                    projected_dx = floor_shift(std::int64_t(dx) * scale, 12);
                    if (row <= 0) first_row_x.push_back(projected_dx);
                    else if (column < first_row_x.size()) projected_dx = first_row_x[column];
                    ++column;
                }
                const u16 px = scale < 0 ? (x + 128 + dx) & 511 : u16(x + 128 + projected_dx);
                const u16 py = u16(y + 128 + (scale < 0 ? dy : floor_shift(std::int64_t(dy) * scale, 12)));
                // The optional wider camera adds 53 pixels at either side.
                // This matches the reversible native-constructor viewport
                // patch; the default preserves the exact original cull.
                const unsigned border = widescreen ? 53 : 0;
                if (u16(px - (96 - border)) <= ((shadow && scale < 0) ? 383 : 351) + border * 2)
                    out.push_back({py, u16((byte(p + 1) | ((alloc >> 7) & 16)) << 8), attr, px,
                                   u16(scale < 0 ? 0x1000 : scale + 0x100), o, lng(o + 0x10), desc,
                                   u32(i | (half << 8) | (unsigned(shadow) << 9))});
                attr += word(p + 2);
            }
        }
    };
    for (u32 o : objects) {
        const unsigned pose = byte(o + 0x20);
        if (pose > 0xfd || (sh1_markvi_visibility::normalize_flags(
                lng(o + 0x10), pose, word(o + 0x2a)) & 0x80))
            continue;
        emit(o, lng(o + 0x1c) + pose * 22, byte(o + 0x28),
             sw(o + 10) > 0 ? word(o + 0x40) : -1, sw(o + 12), sw(o + 14), false);
    }
    // Native second pass: ground shadows, after every object's body. Keep the
    // original depth lookup and rounding, independently of the body's height.
    for (u32 o : objects) {
        const unsigned pose = byte(o + 0x20);
        // The same verified depth budget also thins these objects' shadows.
        // Preserve the independent no-shadow bit and every other hide reason.
        if (pose > 0xfd || (sh1_markvi_visibility::normalize_flags(
                lng(o + 0x10), pose, word(o + 0x2a)) & 0x84))
            continue;
        const int depth = sw(o + 10);
        const int factor = sw(0x3c63e2 + floor_shift(depth, 4) * 2);
        const int y = signed16(u16(floor_shift(std::int64_t(sw(0xff40a2)) * factor, 16) + sw(0xff40a4)));
        u32 desc = 0x1304;
        int scale = -1;
        if (depth > 0) {
            const unsigned levels = byte(0x12f9);
            if (!levels)
                return false;
            const unsigned width = byte(0x12d8 + levels * 22 + 6);
            const unsigned f = word(0x3c7104 + (depth >> 6) * 2);
            unsigned lod = (levels * f) >> 11;
            if (lod >= levels) lod = levels - 1;
            desc = 0x12ee + lod * 22;
            const int lookup = (int(width) - 1) * 32 + int(byte(desc + 6)) - 1;
            scale = u16((f * word(0x3c6904 + lookup * 2)) >> 12);
        }
        emit(o, desc, 0, scale, sw(o + 12), y, true);
    }
    return true;
}

} // namespace sh1_markvi
