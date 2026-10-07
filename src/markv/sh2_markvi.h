// license:GPL-2.0-or-later
#pragma once

#include <cstdint>
#include <unordered_set>
#include <unordered_map>
#include <algorithm>
#include <vector>

namespace sh2_markvi {

// Host records have no SAT link or transform-table index. The transform belongs
// to the record itself, so neither list length nor zoom count wraps at 128.
struct sprite {
    std::uint16_t y, size, attr, x, zoom;
    // Presentation identity; never an index into guest VRAM or a quota.
    std::uint32_t owner = 0, routine = 0, descriptor = 0, part = 0;
};

// Translation of SH2 13B000..13D21E, before its 40/80-entry partitioning.
// Read returns a big-endian guest word. It must read an emitter-entry snapshot,
// not live objects (the game can update those before the next SAT upload).
template<class Read> bool build(Read read, std::vector<sprite> &out)
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
    const u32 tile_table = lng(0x13b78e); // Also follows the optional SH1 explosion cache relocation.
    out.clear();
    std::vector<u32> objects;
    std::unordered_set<u32> seen;
    for (u32 o = lng(0xff38f2) & 0xffffff; o; o = lng(o + 0x18) & 0xffffff) {
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
            u16 attr = mirror ? u16(((flags << 11) & 0xc000) + (byte(o + 0x22) << 13) + (alloc & 0x7ff) + half * 0x800) : base;
            for (unsigned i = 0; i < count; ++i) {
                const u32 p = parts + i * 12;
                int dx = sw(p + ((flags & 1) ? 8 : 4));
                int dy = sw(p + ((flags & 2) ? 10 : 6));
                if (mirror) {
                    dx = signed16(u16(sw(p + (half ? 8 : 4)) + (half ? -1 : 1) * int(byte(desc + 6)) * 4));
                    dy = sw(p + 6);
                }
                const u16 px = scale < 0 ? (x + 128 + dx) & 511 : u16(x + 128 + floor_shift(std::int64_t(dx) * scale, 12));
                const u16 py = u16(y + 128 + (scale < 0 ? dy : floor_shift(std::int64_t(dy) * scale, 12)));
                // Preserve the native offscreen test; it isn't a sprite budget.
                if (u16(px - 96) <= ((shadow && scale < 0) ? 383 : 351))
                    out.push_back({py, u16((byte(p + 1) | ((alloc >> 7) & 16)) << 8), attr, px,
                                   u16(scale < 0 ? 0x1000 : scale + 0x100), o, lng(o + 0x10), desc,
                                   u32(i | (half << 8) | (unsigned(shadow) << 9))});
                attr += word(p + 2);
            }
        }
    };
    for (u32 o : objects) {
        const unsigned pose = byte(o + 0x20);
        if (pose > 0xfd || (byte(o + 0x2b) & 0x80))
            continue;
        emit(o, lng(o + 0x1c) + pose * 22, byte(o + 0x28),
             sw(o + 10) > 0 ? word(o + 0x40) : -1, sw(o + 12), sw(o + 14), false);
    }
    // Native second pass: ground shadows, after every object's body. Keep the
    // original depth lookup and rounding, independently of the body's height.
    for (u32 o : objects) {
        if (byte(o + 0x20) > 0xfd || (byte(o + 0x2b) & 4))
            continue;
        const int depth = sw(o + 10);
        const int factor = sw(0x365944 + floor_shift(depth, 4) * 2);
        const int y = signed16(u16(floor_shift(std::int64_t(sw(0xff38a2)) * factor, 16) + sw(0xff38a4)));
        u32 desc = 0x72e;
        int scale = -1;
        if (depth > 0) {
            const unsigned levels = byte(0x723);
            if (!levels)
                return false;
            const unsigned width = byte(0x702 + levels * 22 + 6);
            const unsigned f = word(0x366666 + (depth >> 6) * 2);
            unsigned lod = (levels * f) >> 11;
            if (lod >= levels) lod = levels - 1;
            desc = 0x718 + lod * 22;
            const int lookup = (int(width) - 1) * 32 + int(byte(desc + 6)) - 1;
            scale = u16((f * word(0x365e66 + lookup * 2)) >> 12);
        }
        emit(o, desc, 0, scale, sw(o + 12), y, true);
    }
    return true;
}

// Only interpolate matching pieces that exist in both snapshots. A hidden,
// destroyed or newly spawned object is never recreated from an old picture.
// Pose/LOD changes deliberately snap to the game's current artwork.
inline std::vector<sprite> interpolate(const std::vector<sprite> &previous,
                                       const std::vector<sprite> &current,
                                       unsigned numerator, unsigned denominator)
{
    auto out = current;
    if (!denominator || numerator >= denominator) return out;
    std::unordered_map<std::uint64_t, const sprite *> by_piece;
    auto key = [](const sprite &s) { return (std::uint64_t(s.owner) << 32) | s.part; };
    for (const auto &s : previous) by_piece.emplace(key(s), &s);
    auto mix = [&](unsigned a, unsigned b) -> std::uint16_t {
        return (std::uint64_t(a) * (denominator - numerator) + std::uint64_t(b) * numerator + denominator / 2) / denominator;
    };
    for (auto &s : out) {
        const auto found = by_piece.find(key(s));
        if (found == by_piece.end()) continue;
        const auto &p = *found->second;
        if (!s.owner || s.routine != p.routine || s.descriptor != p.descriptor ||
            s.size != p.size || (s.attr & 0xf800) != (p.attr & 0xf800)) continue;
        // Screen-coordinate wrapping and large discontinuities are cuts, not
        // travel across the screen. This guard affects only optional smoothing.
        const int dx = int(s.x) - int(p.x), dy = int(s.y) - int(p.y);
        if (dx < -128 || dx > 128 || dy < -128 || dy > 128 ||
            ((s.zoom ^ p.zoom) & 0x8000)) continue;
        s.x = mix(p.x, s.x); s.y = mix(p.y, s.y);
        s.zoom = mix(p.zoom, s.zoom);
    }
    return out;
}

} // namespace sh2_markvi
