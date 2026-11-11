#include "scene_sprites.hpp"

#include "bus.hpp"

#include <algorithm>
#include <bit>

namespace markv {
namespace {

struct Layout {
    unsigned list, entry, alternate_entry, finish;
    unsigned selector, head_pointer, second_head;
    std::array<unsigned, 2> overflow;
    unsigned tiles, ground, ground_scale, ground_y;
    unsigned shadow_fixed, shadow_lods, shadow_depth, shadow_reciprocal;
};

constexpr std::array layouts{
    Layout{0xff40b8, 0x170344, 0x170476, 0x170836, 0xff1be0, 0xff1210, 0xff1ec8,
           {0xff16dc, 0xff195e}, 0xff3d16, 0x3c63e2, 0xff40a2, 0xff40a4,
           0x1304, 0x12ee, 0x3c7104, 0x3c6904},
    Layout{0xff38f2, 0x13b058, 0x13b18a, 0x13b574, 0xff387c, 0xff0e00, 0xff3080,
           {0xff118a, 0xff140c}, 0x13b78e, 0x365944, 0xff38a2, 0xff38a4,
           0x72e, 0x718, 0x366666, 0x365e66},
};

constexpr unsigned ram_start = 0xff0000;
constexpr unsigned last_object = 0xffffb4;
constexpr unsigned bank_mask = 0xffffff;

bool is_object(unsigned address)
{
    return address >= ram_start && address <= last_object && !(address & 1);
}

bool scene_data(unsigned address, unsigned size)
{
    return !(address & 1) && (address <= 0x400000 - size ||
           (address >= 0xfe0000 && address <= 0x1000000 - size));
}

int signed_word(unsigned word)
{
    return std::bit_cast<std::int16_t>(Word(word));
}

int project(int position, unsigned scale)
{
    return int((std::int64_t(position) * scale) >> 12);
}

bool sh1_thinning(unsigned handler)
{
    switch (handler) {
    case 0x1246c8: case 0x1247f0: case 0x124ae4: case 0x124e20: case 0x12510e: case 0x1e41d8:
        return true;
    default:
        return false;
    }
}

Word geometry_word(Word value, unsigned index)
{
    return (index & 3) == 1 ? Word(value & 0xff00) : value;
}

} // namespace

void SceneSprites::clear()
{
    for (auto &bank : banks)
        bank.ready = false;
    presented.ready = false;
    building = banks.size();
    boss_thinning.reset();
    blinking_player = 0;
}

bool SceneSprites::construct(Bus &bus, unsigned game, std::vector<SpritePiece> &out)
{
    const Layout &layout = layouts[game - 1];
    const bool first_game = game == 1;
    const unsigned tiles = first_game ? layout.tiles : bus.read32(layout.tiles);
    out.clear();
    objects.clear();
    visited.reset();
    for (unsigned object = bus.read32(layout.list) & bank_mask; object; object = bus.read32(object + 0x18) & bank_mask) {
        if (!is_object(object) || visited.test((object - ram_start) / 2))
            return false;
        visited.set((object - ram_start) / 2);
        objects.push_back(object);
    }

    const auto emit = [&](unsigned object, unsigned desc, int x, int y, int scale, bool shadow) {
        if (!scene_data(desc, 22))
            return false;
        const unsigned count = bus.read8(desc + 10);
        const unsigned parts = bus.read32(desc + 12);
        const unsigned allocation = tiles + 2 * bus.read16(desc + 8);
        if (count && (!scene_data(parts, count * 12) || !scene_data(allocation, 2)))
            return false;
        if (!count)
            return true;
        const Word tile = bus.read16(allocation);
        const unsigned flags = shadow ? 0 : bus.read8(object + 0x28);
        const unsigned palette = shadow ? 3 : bus.read8(object + 0x22);
        const bool mirrored = (flags & 7) >= 4;
        const bool scaled = scale >= 0;
        const unsigned zoom = scaled ? Word(scale + 0x100) & 0x7fff : 4096;
        const unsigned x_step = std::min(4096u, zoom) / 64;
        const unsigned y_step = zoom / 64;
        if (!x_step || !y_step)
            return true;
        // Capture once for either aspect ratio. The rasterizer clips the list
        // to the current viewport, so an aspect change need not rebuild it.
        const int left_limit = -32 - int(wide_border);
        const int right_limit = ((shadow && !scaled) ? 351 : 319) + int(wide_border);

        for (unsigned half = 0; half < (mirrored ? 2u : 1u); ++half) {
            unsigned attributes = flags << 11;
            if (mirrored) {
                attributes &= 0xc000;
                if (half)
                    attributes = first_game ? ((flags << 11) & 0x1000) | 0x0800 : attributes | 0x0800;
            }
            Word descriptor = (tile & 0x7ff) + (palette << 13) + attributes;
            std::array<int, 256> first_row;
            int first_y = 0, last_y = 0;
            unsigned row_width = 0, column = 0;
            bool top_row = true;
            for (unsigned i = 0; i < count; ++i) {
                const unsigned part = parts + 12 * i;
                const bool flip_x = mirrored ? half != 0 : (flags & 1) != 0;
                const bool flip_y = !mirrored && (flags & 2);
                int dx = signed_word(bus.read16(part + (flip_x ? 8 : 4)));
                const int dy = signed_word(bus.read16(part + (flip_y ? 10 : 6)));
                if (mirrored)
                    dx = signed_word(dx + (half ? -4 : 4) * int(bus.read8(desc + 6)));
                int projected_x = scaled ? project(dx, unsigned(scale)) : dx;
                if (first_game && scaled) {
                    if (i == 0)
                        first_y = dy;
                    if (dy != last_y) {
                        top_row = top_row && dy == first_y;
                        column = 0;
                        last_y = dy;
                    }
                    if (top_row)
                        first_row[row_width++] = projected_x;
                    else if (column < row_width)
                        projected_x = first_row[column];
                    ++column;
                }
                const int screen_x = scaled ? signed_word(x + projected_x) : ((x + 128 + dx) & 511) - 128;
                if (screen_x >= left_limit && screen_x <= right_limit) {
                    const Word screen_y = y + 128 + (scaled ? project(dy, unsigned(scale)) : dy);
                    const Word shape = (bus.read8(part + 1) | ((tile >> 7) & 16)) << 8;
                    const auto identity = (std::uint64_t(desc) << 26) |
                        (std::uint64_t(object & 0xffff) << 10) | (unsigned(shadow) << 9) | (half << 8) | i;
                    out.push_back({screen_x, screen_y, shape, descriptor, x_step, y_step, identity});
                }
                descriptor += bus.read16(part + 2);
            }
        }
        return true;
    };

    // Body pieces precede the ground-shadow pass; both keep object-chain order.
    for (const bool shadow : {false, true}) {
        for (const unsigned object : objects) {
            unsigned pose = bus.read8(object + 0x20);
            if (pose == 0xff && object == blinking_player &&
                bus.read32(object + 0x10) == blinking_handler)
                pose = visible_player_pose;
            if (pose >= 0xfe)
                continue;
            unsigned flags = bus.read8(object + 0x2b);
            if (flags & 0x80) {
                const unsigned handler = bus.read32(object + 0x10);
                const bool display_budget = first_game ? sh1_thinning(handler) :
                    handler == 0x16d6ea && bus.read32(object + 0x1c) == 0x17c4 &&
                    boss_thinning.test((object - ram_start) / 2);
                if (display_budget)
                    flags &= ~0x80u;
            }
            const unsigned hidden_mask = shadow ? (first_game ? 0x84 : 0x04) : 0x80;
            if (flags & hidden_mask)
                continue;

            const int depth = signed_word(bus.read16(object + 10));
            const int x = signed_word(bus.read16(object + 12));
            int y = signed_word(bus.read16(object + 14));
            int scale = -1;
            unsigned desc = layout.shadow_fixed;
            if (shadow) {
                const int ground = signed_word(bus.read16(layout.ground + (depth >> 4) * 2));
                const int slope = signed_word(bus.read16(layout.ground_scale));
                y = signed_word(((std::int64_t(slope) * ground) >> 16) + bus.read16(layout.ground_y));
                if (depth > 0) {
                    const unsigned levels = bus.read8(layout.shadow_lods + 11);
                    if (!levels)
                        return false;
                    const unsigned f = bus.read16(layout.shadow_depth + (depth >> 6) * 2);
                    desc = layout.shadow_lods + 22 * std::min(levels - 1, (levels * f) >> 11);
                    const int width = bus.read8(layout.shadow_lods + 22 * (levels - 1) + 6);
                    const int index = (width - 1) * 32 + int(bus.read8(desc + 6)) - 1;
                    scale = Word((std::uint32_t(f) * bus.read16(layout.shadow_reciprocal + index * 2)) >> 12);
                }
            } else {
                desc = bus.read32(object + 0x1c) + 22 * pose;
                if (depth > 0)
                    scale = bus.read16(object + 0x40);
            }
            if (!emit(object, desc, x, y, scale, shadow))
                return false;
        }
    }
    return true;
}

void SceneSprites::instruction(Bus &bus, unsigned game, unsigned pc, unsigned a0, unsigned a2, unsigned d4, Word status)
{
    const Layout &layout = layouts[game - 1];
    if (pc == layout.entry || pc == layout.alternate_entry) {
        building = bus.read16(layout.selector) & 1;
        auto &bank = banks[building];
        bank.ready = false;
        bank.source = building ? layout.second_head : bus.read32(layout.head_pointer) & bank_mask;
        if (!construct(bus, game, bank.pieces))
            building = banks.size();
        return;
    }
    if (pc == layout.finish && building < banks.size()) {
        auto &bank = banks[building];
        building = banks.size();
        if (bank.source < 0xfe0000 || !scene_data(bank.source, sat_words * 2))
            return;
        for (unsigned i = 0; i < sat_words; ++i)
            bank.signature[i] = geometry_word(bus.read16(bank.source + 2 * i), i);
        bank.ready = true;
        return;
    }

    const bool player_blink = game == 1 ? pc == 0x1dd588 || pc == 0x1dda54 : pc == 0x1794e2;
    if (player_blink && is_object(a2 & bank_mask)) {
        // SH1's visible branches store pose 0; SH2 alternates pose 9 and FF.
        // Restore the drawing in the host list while leaving the guest pose,
        // hit state and collision timing under game control.
        blinking_player = a2 & bank_mask;
        blinking_handler = bus.read32(blinking_player + 0x10);
        visible_player_pose = game == 1 ? 0 : 9;
    }

    // SH2 stage 7 uses the same flag for quota thinning and spatial hiding.
    // Record the executed branch before another actor can move its leader.
    if (game == 2 && (pc == 0x16d774 || pc == 0x16d778 || pc == 0x16d832)) {
        const unsigned object = a0 & bank_mask;
        if (is_object(object)) {
            const auto index = (object - ram_start) / 2;
            if (pc == 0x16d774 && (d4 & 1) && !(status & 4))
                boss_thinning.set(index);
            if (pc == 0x16d778 || (pc == 0x16d832 && !(status & 5)))
                boss_thinning.reset(index);
        }
    }
}

void SceneSprites::upload(Bus &bus, unsigned game, unsigned source, unsigned dest, unsigned words, unsigned stride)
{
    const unsigned table = (bus.video.reg[5] & 127) * 512;
    if (stride != 2) {
        if (words)
            presented.ready = false;
        return;
    }
    if (!words || (dest < table && words * 2 <= table - dest) ||
        (dest >= table + sat_words * 2 && dest + words * 2 <= 0x10000))
        return;
    source &= bank_mask;
    const auto &layout = layouts[game - 1];
    if (presented.ready && table == front_table && words <= sat_words && !(words & 3) &&
        source == layout.overflow[front_bank] && dest == table + (sat_words - words) * 2) {
        // The published list already contains the tail. The matching overflow
        // upload is allowed to replace native table entries within that tail.
        bool prefix_matches = true;
        for (unsigned i = 0; i < sat_words - words; ++i)
            prefix_matches &= geometry_word(bus.video.vram[table / 2 + i], i) == presented.signature[i];
        if (prefix_matches)
            return;
    }
    presented.ready = false;
    if (dest != table || words != sat_words)
        return;
    for (unsigned slot = 0; slot < banks.size(); ++slot) {
        auto &bank = banks[slot];
        if (!bank.ready || bank.source != source)
            continue;
        bool matches = true;
        for (unsigned i = 0; i < sat_words; ++i)
            matches &= geometry_word(bus.read16(source + 2 * i), i) == bank.signature[i];
        if (!matches)
            continue;
        // Keep a producer's current list available when its bank is reused for
        // more than one refresh. Copies occur once per upload, never per line.
        presented.pieces = bank.pieces;
        presented.signature = bank.signature;
        presented.ready = true;
        front_bank = slot;
        front_table = table;
        ++generation;
        return;
    }
}

void SceneSprites::vram_write(unsigned address)
{
    if (presented.ready && address >= front_table && address < front_table + sat_words * 2)
        presented.ready = false;
}

SpriteList SceneSprites::displayed(unsigned table) const
{
    if (presented.ready && front_table == table)
        return {true, presented.pieces, generation};
    return {};
}

} // namespace markv
