// license:GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

namespace markv {
namespace sh2_explosion_detail {
inline std::uint16_t word(const std::uint8_t *p) { return (std::uint16_t(p[0]) << 8) | p[1]; }
inline std::uint32_t longword(const std::uint8_t *p) { return (std::uint32_t(word(p)) << 16) | word(p + 2); }
inline void put_word(std::uint8_t *p, std::uint16_t v) { p[0] = v >> 8; p[1] = v; }
inline void put_long(std::uint8_t *p, std::uint32_t v) { put_word(p, v >> 16); put_word(p + 2, v); }

// Artwork and palette data are read from the authenticated donor. Generated
// visual adapters call the original SH2 motion, lifetime and cleanup handlers.
constexpr std::uint32_t constructor = 0x380100, update = 0x380300;
constexpr std::uint32_t particle_update = 0x380400, tracked_update = 0x380500;
constexpr std::uint32_t ordinary_pending = 0x380600;
constexpr std::uint32_t trampoline = 0x380700, tick = 0x380800;
constexpr std::uint32_t initialize = 0x380a00, particle_pending = 0x380c00;
constexpr std::uint32_t tracked_pending = 0x380d00, select_lod = 0x380e00;
constexpr std::uint32_t handler = 0x381000;
constexpr std::uint32_t capture_cache = 0x381200, reset_cursor = 0x381280;
// Cover every direct initializer of the three native explosion handlers.
// The shared constructor at 139B84 is wrapped separately, without actor filters.
// Controllers, score, damage, movement and cleanup remain native.
constexpr std::uint32_t ordinary_sites[] = {
    0x114d94, 0x15840e, 0x158738, 0x158a62, 0x15e4c4, 0x15e6e2, 0x16ec0c
};
constexpr std::uint32_t particle_sites[] = {0x18fc88, 0x18fe36};
constexpr std::uint32_t tracked_sites[] = {
    0x0cba62, 0x0cbc24, 0x137c88, 0x158d9a, 0x164910,
    0x16d53c, 0x16d8bc, 0x16deca, 0x17328c, 0x173b26,
    0x173dc6, 0x18bb30, 0x194ef4, 0x19550c, 0x1956a2
};
constexpr std::uint32_t clock_sites[] = {
    0x09d8b0, 0x09ec9e, 0x09ee8c, 0x09f2d2, 0x09f2ec, 0x165d86,
    0x175f86, 0x177264, 0x178f3c, 0x18f060, 0x18f654
};
constexpr std::uint32_t descriptors = 0x382000, parts_begin = 0x382400;
constexpr std::uint32_t pixels_begin = 0x384000, palette = 0x39c000;
constexpr std::uint32_t cache_base = 0xfe0000, phase = 0xfe0002, quotient = 0xfe0004;
constexpr std::uint32_t palette_state = 0xfe0008, activations = 0xfe000c;
constexpr std::uint32_t fallbacks = 0xfe0010, palette_colour = 0xfe0014;
constexpr std::uint32_t slots = 0xfe0100;
// Replace the 212 native explosion tiles in the permanent common allocation
// with all 268 donor tiles. The following assets move by exactly 56 tiles.
constexpr std::uint16_t extra_tiles = 56, native_wave_base = 978;
constexpr std::uint16_t modified_wave_base = native_wave_base + extra_tiles;

struct code {
    std::uint8_t *rom;
    std::uint32_t at;
    void w(std::uint16_t v) { put_word(rom + at, v); at += 2; }
    void l(std::uint32_t v) { put_long(rom + at, v); at += 4; }
    void absolute(std::uint16_t op, std::uint32_t address) { w(op); l(address); }
    std::uint32_t branch(std::uint16_t op) { w(op); const auto p = at; w(0); return p; }
    void target(std::uint32_t p) { put_word(rom + p, std::uint16_t(at - p)); }
};

} // namespace sh2_explosion_detail

// Apply only to an already compatibility-patched, big-endian SH2 image in a
// 4 MiB padded buffer. The caller authenticates both original ROM SHA-1 values
// and applies this transactionally. False means no playable candidate was made.
inline bool apply_sh2_enemy_explosions(std::uint8_t *rom, std::size_t capacity,
                                     const std::uint8_t *donor, std::size_t donor_size)
{
    using namespace sh2_explosion_detail;
    if (!rom || !donor || capacity < 0x400000 || donor_size != 0x3e0000)
        return false;
    const std::uint8_t expected_constructor[] = {0x48,0xe7,0x30,0x20,0x20,0x6f,0x00,0x10};
    const std::uint8_t expected_tick[] = {0x52,0xb9,0x00,0xff,0x38,0x7e};
    if (std::memcmp(rom + 0x139b84, expected_constructor, 8) ||
        word(donor + 0x1d7404) != 0x48e7 || word(donor + 0x1d7406) != 0x3c3c)
        return false;
    for (auto site : clock_sites)
        if (std::memcmp(rom + site, expected_tick, 6))
            return false;

    for (auto site : ordinary_sites)
        if (word(rom + site) != 0x217c || longword(rom + site + 2) != 0x137f0a || word(rom + site + 6) != 0x10 ||
            longword(rom + site + 0x1a) != 0x117c0001 || word(rom + site + 0x1e) != 0x22)
            return false;
    for (auto site : particle_sites)
        if (word(rom + site) != 0x217c || longword(rom + site + 2) != 0x137afc || word(rom + site + 6) != 0x10 ||
            longword(rom + site + 0x1a) != 0x117c0001 || word(rom + site + 0x1e) != 0x22)
            return false;
    for (auto site : tracked_sites)
        if (word(rom + site) != 0x217c || longword(rom + site + 2) != 0x137cf0 || word(rom + site + 6) != 0x10 ||
            longword(rom + site + 0x1a) != 0x117c0001 || word(rom + site + 0x1e) != 0x22)
            return false;

    // Authenticated common-loader and absolute script-cursor reset operands.
    if (word(rom + 0xaf6f8) != 0x1639 || longword(rom + 0xaf6fa) != 0x74f ||
        word(rom + 0xaf724) != 0x3039 || longword(rom + 0xaf726) != 0xff3842 ||
        word(rom + 0xaf730) != 0x45f9 || longword(rom + 0xaf732) != 0x744 ||
        longword(rom + 0xaf796) != 0x76001639 || longword(rom + 0xaf79a) != 0x791 ||
        longword(rom + 0x9ff1e) != 0x33fc03d2 || longword(rom + 0x9ff22) != 0xff3842 ||
        longword(rom + 0x175e92) != 0x33fc03d2 || longword(rom + 0x175e96) != 0xff3842 ||
        word(rom + 0x191bfa) != 0x33c1 || longword(rom + 0x191bfc) != 0xff3842)
        return false;

    // Validate and record every tile-table operand before changing anything.
    // All 190 original references are LEA absolute or MOVE.L immediate.
    std::vector<std::uint32_t> table_operands;
    for (std::uint32_t p = 2; p + 4 <= 0x380000; p += 2) {
        if (longword(rom + p) != 0xff3542)
            continue;
        const auto op = word(rom + p - 2);
        if ((op & 0xf1ff) != 0x41f9 && (op & 0xf1ff) != 0x203c)
            return false;
        table_operands.push_back(p);
    }
    if (table_operands.size() != 190)
        return false;

    for (unsigned slot = 0; slot < 384; ++slot)
        if (word(rom + 0x458 + slot * 22 + 8) != slot)
            return false;

    constexpr std::uint16_t counts[] = {4,30,80,154};
    std::uint32_t pixels = pixels_begin, parts = parts_begin;
    for (unsigned pose = 0; pose < 11; ++pose) {
        for (unsigned lod = 0; lod < 4; ++lod) {
            const auto old = 0xd84 + pose * 88 + lod * 22;
            const auto source = longword(donor + old);
            const auto source_parts = longword(donor + old + 12);
            const auto count = word(donor + old + 4);
            const auto part_count = donor[old + 10];
            if (count != counts[lod] || source > donor_size || count * 32u > donor_size - source ||
                source_parts > donor_size || part_count * 12u > donor_size - source_parts ||
                parts + part_count * 12u > pixels_begin)
                return false;
            unsigned total = 0;
            for (unsigned i = 0; i < part_count; ++i) {
                const auto *piece = donor + source_parts + i * 12;
                const auto size = word(piece);
                if (size > 15 || word(piece + 2) != (((size >> 2) & 3) + 1) * ((size & 3) + 1))
                    return false;
                total += word(piece + 2);
            }
            if (total != count)
                return false;
            parts += part_count * 12;
        }
    }

    for (auto p : table_operands)
        put_long(rom + p, slots);
    parts = parts_begin;
    for (unsigned pose = 0; pose < 11; ++pose) {
        for (unsigned lod = 0; lod < 4; ++lod) {
            const auto old = 0xd84 + pose * 88 + lod * 22;
            const auto dest = descriptors + pose * 88 + lod * 22;
            const auto bytes = counts[lod] * 32u;
            const auto n = donor[old + 10];
            std::copy_n(donor + old, 22, rom + dest);
            std::copy_n(donor + longword(donor + old), bytes, rom + pixels);
            std::copy_n(donor + longword(donor + old + 12), n * 12, rom + parts);
            put_long(rom + dest, pixels);
            put_word(rom + dest + 8, 0x180 + lod);
            put_long(rom + dest + 12, parts);
            for (unsigned i = 0; i < n; ++i)
                put_word(rom + parts + i * 12, word(rom + parts + i * 12) | 0x40);
            pixels += bytes;
            parts += n * 12;
        }
    }
    std::copy_n(donor + 0x393aea, 32, rom + palette);

    // Initializers can be rendered before their first update. Their native
    // descriptors must already select valid donor geometry and shared slots.
    // Retain each native family's LOD count for its unchanged projection code.
    constexpr unsigned initial_lods[] = {0, 1, 3, 1, 3};
    for (unsigned i = 0; i < 5; ++i) {
        auto *dest = rom + 0x744 + i * 22;
        std::copy_n(rom + descriptors + initial_lods[i] * 22, 22, dest);
        dest[11] = i < 3 ? 3 : 2;
    }

    // Original entry, callable without recursing through the installed hook.
    std::copy_n(expected_constructor, 8, rom + trampoline);
    code c{rom, trampoline + 8}; c.absolute(0x4ef9, 0x139b8c);

    // Every call already requests a native explosion: do not classify its
    // previous actor, reaction byte or collision caller. This includes scenery,
    // player collisions and dynamically created objects.
    c.at = constructor;
    c.absolute(0x4a79, cache_base); auto no_room = c.branch(0x6700);
    c.w(0x2f2f); c.w(4); c.absolute(0x4eb9, trampoline); c.w(0x588f);
    c.w(0x4878); c.w(1); // Cold preload is needed before the first ordinary update.
    c.w(0x2f3c); c.l(update); c.w(0x2f2f); c.w(12);
    c.absolute(0x4eb9, initialize); c.w(0x4fef); c.w(12); c.w(0x4e75);
    c.target(no_room); c.absolute(0x52b9, fallbacks);
    c.absolute(0x4ef9, trampoline);
    if (c.at >= update) return false;

    // Execute the host handler first, including unlink/free and boss accounting.
    // Every native cleanup exit sets state 20 to FF. Never rewrite that object.
    // Before the common cache is initialized retain the native descriptor;
    // do not restart its lifetime, delay, velocity or boss completion counter.
    const auto emit_wrapper = [&](std::uint32_t dest, std::uint32_t native,
                                  std::uint32_t steady, bool pending) {
        c.at = dest; c.w(0x48e7); c.w(0x3020); // d2-d3/a2.
        c.w(0x246f); c.w(0x10); c.w(0x242a); c.w(0x1c);
        c.w(0x2f0a); c.absolute(0x4eb9, native); c.w(0x588f);
        c.w(0x0c2a); c.w(0xff); c.w(0x20); auto dead = c.branch(0x6700);
        c.absolute(0x4a79, cache_base); auto no_cache = c.branch(0x6700);
        if (pending) {
            c.w(0x42a7); // No preload: this wrapper animates in the same update.
            c.w(0x2f3c); c.l(steady); c.w(0x2f0a);
            c.absolute(0x4eb9, initialize); c.w(0x4fef); c.w(12);
        } else {
            c.w(0x2542); c.w(0x1c); // Keep the shared donor descriptor between uploads.
        }
        c.w(0x2f0a); c.absolute(0x4eb9, handler); c.w(0x588f);
        auto done = c.branch(0x6000);
        c.target(no_cache); c.w(0x257c); c.l(native); c.w(0x10);
        c.w(0x157c); c.w(1); c.w(0x22); c.absolute(0x52b9, fallbacks);
        c.w(0x2f0a); c.absolute(0x4eb9, select_lod); c.w(0x588f);
        c.target(dead); c.target(done); c.w(0x4cdf); c.w(0x040c); c.w(0x4e75);
        return c.at < dest + 0x100;
    };
    if (!emit_wrapper(update, 0x137f0a, update, false) ||
        !emit_wrapper(particle_update, 0x137afc, particle_update, false) ||
        !emit_wrapper(tracked_update, 0x137cf0, tracked_update, false) ||
        !emit_wrapper(ordinary_pending, 0x137f0a, update, true) ||
        !emit_wrapper(particle_pending, 0x137afc, particle_update, true) ||
        !emit_wrapper(tracked_pending, 0x137cf0, tracked_update, true)) return false;

    // Visual initialization takes (object, steady_method, preload). Preload only when no
    // other live mod effect is using the shared cache. The first update still
    // initializes its clock quotient, exactly as a new SH1 shared animation.
    c.at = initialize; c.w(0x48e7); c.w(0x3c3c);
    c.w(0x246f); c.w(0x24);
    c.w(0x7a00); c.absolute(0x2079, 0xff38f2); c.w(0x303c); c.w(255);
    const auto cache_scan = c.at;
    c.w(0xb1fc); c.l(0xff0000); auto cache_scan_low = c.branch(0x6500);
    c.w(0xb1fc); c.l(0xffffb4); auto cache_scan_high = c.branch(0x6400);
    c.w(0xb1ca); auto cache_self = c.branch(0x6700);
    c.w(0x0ca8); c.l(update); c.w(0x10); auto cache_ordinary = c.branch(0x6700);
    c.w(0x0ca8); c.l(particle_update); c.w(0x10); auto cache_particle = c.branch(0x6700);
    c.w(0x0ca8); c.l(tracked_update); c.w(0x10); auto cache_other = c.branch(0x6600);
    c.target(cache_ordinary); c.target(cache_particle);
    c.w(0x0c28); c.w(0xfe); c.w(0x20); auto cache_dead = c.branch(0x6400);
    c.w(0x7a01); auto cache_live = c.branch(0x6000);
    c.target(cache_self); c.target(cache_other); c.target(cache_dead);
    c.w(0x2068); c.w(0x18); c.w(0x51c8); c.w(std::uint16_t(cache_scan - c.at));
    c.target(cache_scan_low); c.target(cache_scan_high); c.target(cache_live);
    c.w(0x256f); c.w(0x28); c.w(0x10);
    c.w(0x157c); c.w(3); c.w(0x22);
    c.absolute(0x4279, phase); c.absolute(0x52b9, activations);
    c.absolute(0x41f9, palette); c.absolute(0x43f9, 0xc004e0);
    c.w(0x700f); const auto palette_loop = c.at;
    c.w(0x32d8); c.w(0x51c8); c.w(std::uint16_t(palette_loop - c.at));
    c.absolute(0x3039, palette_colour); c.absolute(0x33c0, 0xc004f0);
    c.w(0x257c); c.l(descriptors); c.w(0x1c);
    c.w(0x4a85); auto keep_live_pixels = c.branch(0x6600);
    // Pending wrappers animate immediately in this same update. Only the
    // ordinary constructor needs a cold preload before its later first update.
    c.w(0x4aaf); c.w(0x2c); auto pending_upload = c.branch(0x6700);
    c.w(0x2f0a); c.absolute(0x4eb9, handler); c.w(0x588f);
    c.target(keep_live_pixels); c.target(pending_upload); c.absolute(0x4279, phase);
    c.w(0x2f0a); c.absolute(0x4eb9, select_lod); c.w(0x588f);
    c.w(0x4cdf); c.w(0x3c3c); c.w(0x4e75);
    if (c.at >= particle_pending) return false;

    // SH1's shared visual state machine: phase zero initializes at this clock;
    // each new (clock >> 2) advances once, and pose eleven remains selected.
    // No donor position, velocity, lifetime, clipping or free-list code is used.
    c.at = handler; c.w(0x48e7); c.w(0x3c3c); c.w(0x246f); c.w(0x24);
    c.w(0x7400); c.absolute(0x3439, phase);
    c.absolute(0x3039, 0xff3880); c.w(0xe448);
    c.w(0x4a42); auto first_pose = c.branch(0x6700);
    c.absolute(0xb079, quotient); auto same_quotient = c.branch(0x6700);
    c.target(first_pose); c.absolute(0x33c0, quotient);
    c.w(0x0c42); c.w(10); auto final_pose = c.branch(0x6200);
    c.w(0x2002); c.w(0xc0fc); c.w(88); c.absolute(0x47f9, descriptors);
    c.w(0xd7c0); c.w(0x254b); c.w(0x1c); // pose base to object's descriptor.
    c.w(0x7800); c.absolute(0x3839, cache_base); c.w(0x7a03);
    c.absolute(0x49f9, slots); c.absolute(0x4bf9, 0x0a2390);
    const auto upload_loop = c.at;
    c.w(0x7000); c.w(0x302b); c.w(4); c.w(0x2f00);
    c.w(0x2004); c.w(0xeb88); c.w(0x0680); c.l(0xd10000);
    c.w(0x2f00); c.w(0x2f13); c.w(0x4e95); c.w(0x4fef); c.w(12);
    c.w(0x7000); c.w(0x302b); c.w(8); c.w(0xd080);
    c.w(0x3204); c.w(0x0241); c.w(0x7ff); c.w(0x0041); c.w(0x800);
    c.w(0x3981); c.w(0x0800);
    c.w(0x7000); c.w(0x302b); c.w(4); c.w(0xd880);
    c.w(0x47eb); c.w(22); c.w(0x51cd); c.w(std::uint16_t(upload_loop - c.at));
    c.w(0x5242); c.absolute(0x33c2, phase);
    c.target(same_quotient); c.target(final_pose);
    c.w(0x2f0a); c.absolute(0x4eb9, select_lod); c.w(0x588f);
    c.w(0x4cdf); c.w(0x3c3c); c.w(0x4e75);
    if (c.at >= capture_cache) return false;

    // The native descriptor-driven scale rule also handles a fallback to the
    // original three-source art. Only LOD/zoom change, never X/Y/Z or projection.
    c.at = select_lod; c.w(0x48e7); c.w(0x3020); c.w(0x246f); c.w(0x10);
    c.w(0x302a); c.w(0x0a); c.w(0xec40); c.w(0x48c0); c.w(0xd080);
    c.absolute(0x41f9, 0x366666); c.w(0x3230); c.w(0x0800);
    c.w(0x206a); c.w(0x1c); c.w(0x7400); c.w(0x1428); c.w(11);
    c.w(0x3601); c.w(0xc6c2); c.w(0x700b); c.w(0xe0ab); c.w(0x5342);
    c.w(0xb642); auto lod_ok = c.branch(0x6300); c.w(0x3602); c.target(lod_ok);
    c.w(0x1543); c.w(0x20); c.w(0xc6fc); c.w(22);
    c.w(0x7000); c.w(0x1030); c.w(0x3806);
    c.w(0x7400); c.w(0x3428); c.w(0x12); c.w(0xd082); c.w(0xd080);
    c.absolute(0x43f9, 0x365e66); c.w(0x3031); c.w(0x0800);
    c.w(0xc2c0); c.w(0x700c); c.w(0xe0a9); c.w(0x3541); c.w(0x40);
    c.w(0x4cdf); c.w(0x040c); c.w(0x4e75);
    if (c.at >= handler) return false;

    // Same game-clock cadence as SH1. Cover every reconstructed increment path,
    // including 18F060 used by active gameplay. A shared subroutine preserves
    // each six-byte call site's continuation and the original ADDQ flags.
    // Keep colour 8 cycling independently of constructors resetting the pose.
    c.at = tick;
    c.absolute(0x52b9, 0xff387e);
    c.w(0x40e7); // Preserve the original ADDQ condition codes, including X.
    c.w(0x48e7); c.w(0xc000); // d0-d1.
    c.absolute(0x2039, 0xff387e); c.w(0x0240); c.w(7); c.w(0x0c40); c.w(2);
    auto tick_done = c.branch(0x6600);
    c.absolute(0x2039, palette_state); c.w(0x0c80); c.l(5); auto normal_cycle = c.branch(0x6300);
    c.absolute(0x42b9, palette_state); c.w(0x700e); auto emit_reset = c.branch(0x6000);
    c.target(normal_cycle); c.w(0x0c80); c.l(2); auto rising = c.branch(0x6200);
    c.w(0x7207); c.w(0x9280); c.w(0xd281); c.w(0x2001); auto emit_falling = c.branch(0x6000);
    c.target(rising); c.w(0x5480); c.w(0xd080);
    c.target(emit_reset); c.target(emit_falling);
    c.absolute(0x52b9, palette_state);
    c.absolute(0x33c0, palette_colour); c.absolute(0x33c0, 0xc004f0);
    c.target(tick_done); c.w(0x4cdf); c.w(3); c.w(0x44df); c.w(0x4e75);

    // Capture the permanent cache at the point where the common loader would
    // have allocated native explosions. Keep its cursor in d0 for the loader.
    c.at = capture_cache; c.absolute(0x3039, 0xff3842);
    c.absolute(0x33c0, cache_base); c.absolute(0x4279, phase);
    c.w(0x48e7); c.w(0x80c0); // Preserve d0/a0-a1 while installing the palette.
    c.absolute(0x41f9, palette); c.absolute(0x43f9, 0xc004e0); c.w(0x700f);
    const auto common_palette_loop = c.at;
    c.w(0x32d8); c.w(0x51c8); c.w(std::uint16_t(common_palette_loop - c.at));
    c.absolute(0x3039, palette_colour); c.absolute(0x33c0, 0xc004f0);
    c.w(0x4cdf); c.w(0x0301); c.w(0x4e75);
    if (c.at >= reset_cursor) return false;
    // Immediate script addresses refer to the original permanent allocation.
    // Saved cursors already contain relocated values and need no adjustment.
    // Preserve the original MOVE's flags, including X, and all registers.
    c.at = reset_cursor; c.absolute(0x33c1, 0xff3842); c.w(0x40e7);
    c.w(0x0c41); c.w(972); auto before_common_end = c.branch(0x6500);
    c.w(0x0679); c.w(extra_tiles); c.l(0xff3842);
    c.target(before_common_end); c.w(0x44df); c.w(0x4e75);

    put_long(rom + 0xaf6fa, descriptors + 11);
    put_word(rom + 0xaf724, 0x4eb9); put_long(rom + 0xaf726, capture_cache);
    put_long(rom + 0xaf732, descriptors);
    // The four donor sizes replace both original explosion families.
    put_word(rom + 0xaf796, 0x6000); put_word(rom + 0xaf798, 0x94);
    put_word(rom + 0x9ff20, modified_wave_base);
    put_word(rom + 0x175e94, modified_wave_base);
    put_word(rom + 0x191bfa, 0x4eb9); put_long(rom + 0x191bfc, reset_cursor);

    for (auto site : ordinary_sites) { put_long(rom + site + 2, ordinary_pending); put_word(rom + site + 0x1c, 3); }
    for (auto site : particle_sites) { put_long(rom + site + 2, particle_pending); put_word(rom + site + 0x1c, 3); }
    for (auto site : tracked_sites) { put_long(rom + site + 2, tracked_pending); put_word(rom + site + 0x1c, 3); }
    put_word(rom + 0x139b84, 0x4ef9); put_long(rom + 0x139b86, constructor);
    put_word(rom + 0x139b8a, 0x4e71);
    for (auto site : clock_sites) {
        put_word(rom + site, 0x4eb9);
        put_long(rom + site + 2, tick);
    }
    return pixels < palette && c.at < descriptors;
}
} // namespace markv
