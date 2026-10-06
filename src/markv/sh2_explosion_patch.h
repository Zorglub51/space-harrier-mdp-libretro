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

// Original guest code and artwork are read from the user's authenticated donor.
// Only the adapter instructions and relocation addresses are distributed here.
constexpr std::uint32_t constructor = 0x380100, update = 0x380300;
constexpr std::uint32_t initial_load = 0x380500, trampoline = 0x380700;
constexpr std::uint32_t tick = 0x380800, handler = 0x381000;
constexpr std::uint32_t clock_sites[] = {
    0x09d8b0, 0x09ec9e, 0x09ee8c, 0x09f2d2, 0x09f2ec, 0x165d86,
    0x175f86, 0x177264, 0x178f3c, 0x18f060, 0x18f654
};
// Direct actor-factory spawn sites whose final collision reaction is zero.
// Scenery uses a different factory; custom boss reactions are not in this list.
struct enemy_spawn { std::uint32_t site, method, descriptor, reaction_clear; };
constexpr enemy_spawn enemy_spawns[] = {
    {0x0a2ea8, 0x0f8ac4, 0x000c56, 0x0a2ec8},
    {0x0a2f0e, 0x0f63ce, 0x000c56, 0x0a2f2e},
    {0x0a2f74, 0x0eb42a, 0x000c56, 0x0a2f94},
    {0x0a2fde, 0x0e8e26, 0x000c56, 0x0a2ffe},
    {0x0a3048, 0x155b68, 0x000df8, 0x0a3068},
    {0x0a30ae, 0x1467a4, 0x000c56, 0x0a30ce},
    {0x0a3114, 0x0af9cc, 0x0013fc, 0x0a3134},
    {0x0a316a, 0x0e7138, 0x000c56, 0x0a318a},
    {0x0a31d4, 0x0b6ff4, 0x000e3a, 0x0a31f4},
    {0x0a32a8, 0x0dae0e, 0x0013fc, 0x0a32c8},
    {0x0a3312, 0x0dbc3e, 0x0013fc, 0x0a3332},
    {0x0a3368, 0x0f1748, 0x000c56, 0x0a3388},
    {0x0a33ce, 0x116256, 0x000f2c, 0x0a33ee},
    {0x0a34bc, 0x0d85c4, 0x0013fc, 0x0a34dc},
    {0x0a3526, 0x14def4, 0x000c56, 0x0a3546},
    {0x0a358c, 0x0b2cbe, 0x000e3a, 0x0a35ac},
    {0x0a35f2, 0x0fdb56, 0x000df8, 0x0a3612},
    {0x0a3658, 0x0d9fde, 0x0013fc, 0x0a3678},
    {0x0a36c2, 0x0f3d8e, 0x000c56, 0x0a36e2},
    {0x0a37ae, 0x0eda2e, 0x000c56, 0x0a37ce},
    {0x0a3814, 0x0dcb7e, 0x0013fc, 0x0a3834},
    {0x0a386a, 0x14bf66, 0x000c56, 0x0a388a},
    {0x0a38d0, 0x0b4c64, 0x000e3a, 0x0a38f0},
    {0x0a3936, 0x1002a8, 0x000df8, 0x0a3956},
    {0x0a399c, 0x0d4d44, 0x0013fc, 0x0a39bc},
    {0x0a3a06, 0x1029fa, 0x000c56, 0x0a3a26},
    {0x0a3a70, 0x114fd4, 0x000f2c, 0x0a3a90},
    {0x0a3b44, 0x0d6baa, 0x0013fc, 0x0a3b64},
    {0x0a3bae, 0x0b0d18, 0x000e3a, 0x0a3bce},
    {0x0a3c14, 0x149fd8, 0x000c56, 0x0a3c34},
    {0x0a3c7a, 0x0fb2d4, 0x000df8, 0x0a3c9a},
    {0x0a3ce0, 0x0e52d0, 0x0013fc, 0x0a3d00},
    {0x0a3dd4, 0x13183a, 0x000ebe, 0x0a3df4},
    {0x0a3e56, 0x14fe84, 0x000df8, 0x0a3e76},
    {0x0a3ebc, 0x185284, 0x000cc4, 0x0a3edc},
    {0x0a452c, 0x0be740, 0x000ebe, 0x0a454c},
    {0x0a4592, 0x0bbd62, 0x000ebe, 0x0a45b2},
    {0x0a469a, 0x0e346c, 0x0013fc, 0x0a46ba},
    {0x0a4770, 0x1174d8, 0x000df8, 0x0a4790},
    {0x0a47d6, 0x0ddecc, 0x0013fc, 0x0a47f6},
    {0x0a482c, 0x0dfa6a, 0x0013fc, 0x0a484c},
    {0x0a4882, 0x0e1608, 0x0013fc, 0x0a48a2},
    {0x0a48d8, 0x135be6, 0x000ebe, 0x0a48f8},
    {0x0a4992, 0x133f2c, 0x000ebe, 0x0a49b2},
    {0x0a4b48, 0x14393a, 0x000db6, 0x0a4b68},
    {0x0a4bae, 0x13ddfc, 0x000cc4, 0x0a4bce},
    {0x0a4c8e, 0x0b9384, 0x000ebe, 0x0a4cae},
    {0x0a4cf4, 0x11d1bc, 0x000db6, 0x0a4d14},
    {0x0a4d5a, 0x0c06da, 0x000ebe, 0x0a4d7a},
    {0x0a4e36, 0x12f148, 0x000ebe, 0x0a4e56},
    {0x0a5ade, 0x185284, 0x000cc4, 0x0a5afe},
};
constexpr std::uint32_t enemy_method_table = 0x380900;
constexpr std::size_t enemy_spawn_count = sizeof(enemy_spawns) / sizeof(enemy_spawns[0]);

constexpr std::uint32_t descriptors = 0x382000, parts_begin = 0x382400;
constexpr std::uint32_t pixels_begin = 0x384000, palette = 0x39c000;
constexpr std::uint32_t cache_base = 0xfe0000, phase = 0xfe0002, quotient = 0xfe0004;
constexpr std::uint32_t palette_state = 0xfe0008, activations = 0xfe000c;
constexpr std::uint32_t fallbacks = 0xfe0010, palette_colour = 0xfe0014;
constexpr std::uint32_t slots = 0xfe0100;
constexpr std::uint16_t first_tile = 0x6f4; // 8576 bytes, bank 1 DE80..FFFF.

struct code {
    std::uint8_t *rom;
    std::uint32_t at;
    void w(std::uint16_t v) { put_word(rom + at, v); at += 2; }
    void l(std::uint32_t v) { put_long(rom + at, v); at += 4; }
    void absolute(std::uint16_t op, std::uint32_t address) { w(op); l(address); }
    std::uint32_t branch(std::uint16_t op) { w(op); const auto p = at; w(0); return p; }
    void target(std::uint32_t p) { put_word(rom + p, std::uint16_t(at - p)); }
};

inline std::uint32_t relocated(std::uint32_t address)
{
    if (address >= 0xd84 && address < 0x114c)
        return descriptors + address - 0xd84;
    switch (address) {
    case 0xff3d0c: return 0xff3882; // Game speed.
    case 0xff1c40: return 0xff38cc; // Horizontal world drift.
    case 0xff1c38: return phase;
    case 0xff1c3c: return quotient;
    case 0xff1c3e: return 0xff3880; // Low word of the homologous SH2 game clock.
    case 0xff1c0a: return cache_base;
    case 0xff3d16: return slots;
    case 0xff40a2: return 0xff38a2;
    case 0xff40a4: return 0xff38a4;
    case 0xff3ca4: return 0xff3310; // SH2 free object list.
    case 0xff4088: return 0xff38ce;
    case 0xff40b8: return 0xff38f2;
    case 0x3c63e2: return 0x365944; // Preserve SH2's projection at its own depths.
    case 0x0c83d4: return 0x0a2390; // Same (source,destination,tile_count) ABI.
    default: return address;
    }
}

inline void copy_relocated(std::uint8_t *rom, const std::uint8_t *donor,
                           std::uint32_t source, std::uint32_t end, std::uint32_t dest)
{
    std::copy(donor + source, donor + end, rom + dest);
    for (std::uint32_t p = source; p + 4 <= end; p += 2) {
        const auto old = longword(donor + p);
        const auto replacement = relocated(old);
        if (old != replacement)
            put_long(rom + dest + p - source, replacement);
    }
}
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

    for (const auto &spawn : enemy_spawns) {
        if (word(rom + spawn.site) != 0x4879 || longword(rom + spawn.site + 2) != spawn.method ||
            word(rom + spawn.site + 6) != 0x4879 || longword(rom + spawn.site + 8) != spawn.descriptor ||
            word(rom + spawn.site + 12) != 0x4eb9 || longword(rom + spawn.site + 14) != 0x13d6b4 ||
            word(rom + spawn.reaction_clear) != 0x4228 || word(rom + spawn.reaction_clear + 2) != 0x23)
            return false;
    }

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
    copy_relocated(rom, donor, 0x1d7404, 0x1d7e84, handler);

    // Original entry, callable without recursing through the installed hook.
    std::copy_n(expected_constructor, 8, rom + trampoline);
    code c{rom, trampoline + 8}; c.absolute(0x4ef9, 0x139b8c);

    for (std::size_t i = 0; i < enemy_spawn_count; ++i)
        put_long(rom + enemy_method_table + i * 4, enemy_spawns[i].method);

    // Both generic collision loops can destroy enemies or scenery. Require a
    // recognized actor method and current reaction zero before either route.
    // Custom callbacks, player collisions and unknown methods remain original.
    c.at = constructor;
    c.w(0x0c97); c.l(0x171f36); auto eligible_a = c.branch(0x6700);
    c.w(0x0c97); c.l(0x172132); auto eligible_b = c.branch(0x6700);
    c.w(0x0c97); c.l(0x1719dc); auto eligible_c = c.branch(0x6700);
    c.w(0x0c97); c.l(0x171e7a); auto ordinary = c.branch(0x6600);
    c.target(eligible_a); c.target(eligible_b); c.target(eligible_c);
    c.w(0x206f); c.w(4); c.w(0x4a28); c.w(0x23); auto nonzero_reaction = c.branch(0x6600);
    c.w(0x2028); c.w(0x10); c.absolute(0x43f9, enemy_method_table);
    c.w(0x323c); c.w(std::uint16_t(enemy_spawn_count - 1));
    const auto method_scan = c.at;
    c.w(0xb099); auto recognized_method = c.branch(0x6700);
    c.w(0x51c9); c.w(std::uint16_t(method_scan - c.at));
    auto unknown_method = c.branch(0x6000);
    c.target(recognized_method);
    c.w(0x0c79); c.w(first_tile); c.l(0xff3842); auto no_room = c.branch(0x6200);
    c.w(0x2f2f); c.w(4); c.absolute(0x4eb9, trampoline); c.w(0x588f);
    c.w(0x48e7); c.w(0x3c3c); // d2-d5/a2-a5, as in the donor handler.
    c.w(0x246f); c.w(0x24);
    // A new effect must not restart another live effect's shared pixels before
    // the donor's first update. With no live effect, preload a defined image;
    // no cached-valid flag survives across stage loads that reuse this VRAM.
    c.w(0x7a00); c.absolute(0x2079, 0xff38f2); c.w(0x303c); c.w(255);
    const auto cache_scan = c.at;
    c.w(0xb1fc); c.l(0xff0000); auto cache_scan_low = c.branch(0x6500);
    c.w(0xb1fc); c.l(0xffffb4); auto cache_scan_high = c.branch(0x6400);
    c.w(0xb1ca); auto cache_self = c.branch(0x6700);
    c.w(0x0ca8); c.l(update); c.w(0x10); auto cache_other = c.branch(0x6600);
    c.w(0x0c28); c.w(0xfe); c.w(0x20); auto cache_dead = c.branch(0x6400);
    c.w(0x7a01); auto cache_live = c.branch(0x6000);
    c.target(cache_self); c.target(cache_other); c.target(cache_dead);
    c.w(0x2068); c.w(0x18); c.w(0x51c8); c.w(std::uint16_t(cache_scan - c.at));
    c.target(cache_scan_low); c.target(cache_scan_high); c.target(cache_live);
    c.w(0x257c); c.l(update); c.w(0x10);
    c.w(0x157c); c.w(3); c.w(0x22);
    c.w(0x33fc); c.w(first_tile); c.l(cache_base);
    c.absolute(0x4279, phase);
    c.absolute(0x52b9, activations);
    c.absolute(0x41f9, palette); c.absolute(0x43f9, 0xc004e0);
    c.w(0x700f); const auto palette_loop = c.at;
    c.w(0x32d8); c.w(0x51c8); c.w(std::uint16_t(palette_loop - c.at));
    c.absolute(0x3039, palette_colour); c.absolute(0x33c0, 0xc004f0);
    c.w(0x4a85); auto keep_live_pixels = c.branch(0x6600);
    c.absolute(0x4eb9, initial_load);
    c.target(keep_live_pixels);
    c.w(0x257c); c.l(descriptors); c.w(0x1c);
    // The first update initializes phase at its own clock in both cases.
    c.absolute(0x4279, phase);
    // Initial LOD/zoom, matching the common game's descriptor-driven selector.
    c.w(0x302a); c.w(0x0a); c.w(0xec40); c.w(0x48c0); c.w(0xd080);
    c.absolute(0x41f9, 0x366666); c.w(0x3230); c.w(0x0800);
    c.w(0x3401); c.w(0xe04a); c.w(0xe24a); c.w(0x0c42); c.w(3);
    auto lod_ok = c.branch(0x6300); c.w(0x7403); c.target(lod_ok);
    c.w(0x1542); c.w(0x20); c.w(0xc4fc); c.w(22);
    c.w(0x206a); c.w(0x1c); c.w(0x7000); c.w(0x1030); c.w(0x2806);
    c.w(0x7600); c.w(0x3628); c.w(0x12); c.w(0xd083); c.w(0xd080);
    c.absolute(0x43f9, 0x365e66); c.w(0x3031); c.w(0x0800);
    c.w(0xc2c0); c.w(0x700c); c.w(0xe0a9); c.w(0x3541); c.w(0x40);
    c.w(0x4cdf); c.w(0x3c3c); c.w(0x4e75);
    c.target(no_room); c.absolute(0x52b9, fallbacks);
    c.target(ordinary); c.target(nonzero_reaction); c.target(unknown_method);
    c.absolute(0x4ef9, trampoline);
    if (c.at >= update) return false;

    // Guard an already-active effect against a later asset load using the cache.
    c.at = update;
    c.w(0x0c79); c.w(first_tile); c.l(0xff3842); auto run = c.branch(0x6300);
    c.w(0x206f); c.w(4);
    c.w(0x217c); c.l(0x137f0a); c.w(0x10);
    c.w(0x217c); c.l(0x744); c.w(0x1c);
    c.w(0x117c); c.w(1); c.w(0x22);
    c.w(0x4268); c.w(0x2e); c.w(0x4268); c.w(8);
    c.absolute(0x52b9, fallbacks); c.absolute(0x4ef9, 0x137f0a);
    c.target(run); c.absolute(0x4ef9, handler);

    // Exact donor pose-zero upload, without advancing the object's position.
    c.at = initial_load; c.w(0x7400);
    copy_relocated(rom, donor, 0x1d7498, 0x1d7528, c.at);
    c.at += 0x90; c.w(0x4e75);

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

    put_word(rom + 0x139b84, 0x4ef9); put_long(rom + 0x139b86, constructor);
    put_word(rom + 0x139b8a, 0x4e71);
    for (auto site : clock_sites) {
        put_word(rom + site, 0x4eb9);
        put_long(rom + site + 2, tick);
    }
    return pixels < palette && c.at < handler;
}
} // namespace markv
