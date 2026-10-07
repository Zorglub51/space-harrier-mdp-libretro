// license:GPL-2.0-or-later
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace sh_widescreen {

// 426 source pixels: the unchanged 320-pixel camera plus 53 on each side.
// The libretro display aspect is 16:9; no world-coordinate/projection constant
// is changed. The native sprite constructor still uses its existing quotas.
inline constexpr unsigned border = 53;
enum class profile { sh1, sh2 };

struct clip_pair {
    std::uint32_t address;
    std::uint16_t offset_opcode, limit_opcode, limit;
};

// Each eight-byte pair either subtracts 96 with ADDI.W or uses LEA -96(A6),
// followed by CMP.W #limit or MOVE.W #limit,D5. These are presentation culls
// in the restored constructors, not object lifetime/collision bounds.
inline constexpr std::array<clip_pair, 18> sh1_pairs{{
    {0x170594, 0x0642, 0x0c42, 351},
    {0x170766, 0x0645, 0x0c45, 351},
    {0x170938, 0x0642, 0x0c42, 351},
    {0x170a24, 0x0642, 0x0c42, 351},
    {0x170b0c, 0x0642, 0x0c42, 351},
    {0x170d0a, 0x4dee, 0x3a3c, 351},
    {0x170dd2, 0x4dee, 0x3a3c, 351},
    {0x1718c0, 0x0644, 0x0c44, 383},
    {0x171b04, 0x0642, 0x0c42, 351},
    {0x171b80, 0x0642, 0x0c42, 351},
    {0x171ba2, 0x0642, 0x0c42, 351},
    {0x171c9a, 0x0642, 0x0c42, 351},
    {0x171cbe, 0x0642, 0x0c42, 351},
    {0x171db6, 0x0642, 0x0c42, 351},
    {0x171dda, 0x0642, 0x0c42, 351},
    {0x171f14, 0x0643, 0x0c43, 351},
    {0x171f80, 0x0642, 0x0c42, 351},
    {0x171fa4, 0x0642, 0x0c42, 351},
}};
inline constexpr std::array<clip_pair, 18> sh2_pairs{{
    {0x13b2a8, 0x0642, 0x0c42, 351},
    {0x13b478, 0x0645, 0x0c45, 351},
    {0x13b64a, 0x0642, 0x0c42, 351},
    {0x13b736, 0x0642, 0x0c42, 351},
    {0x13b81e, 0x0642, 0x0c42, 351},
    {0x13ba1c, 0x4dee, 0x3a3c, 351},
    {0x13bae4, 0x4dee, 0x3a3c, 351},
    {0x13c5d2, 0x0644, 0x0c44, 383},
    {0x13c816, 0x0642, 0x0c42, 351},
    {0x13c892, 0x0642, 0x0c42, 351},
    {0x13c8b4, 0x0642, 0x0c42, 351},
    {0x13c9ac, 0x0642, 0x0c42, 351},
    {0x13c9d0, 0x0642, 0x0c42, 351},
    {0x13cac8, 0x0642, 0x0c42, 351},
    {0x13caec, 0x0642, 0x0c42, 351},
    {0x13cc26, 0x0643, 0x0c43, 351},
    {0x13cc92, 0x0642, 0x0c42, 351},
    {0x13ccb6, 0x0642, 0x0c42, 351},
}};

struct immediate_site {
    std::uint32_t address;
    std::uint16_t original, wide;
};

constexpr std::array<immediate_site, 36> make_sites(const std::array<clip_pair, 18> &pairs)
{
    std::array<immediate_site, 36> result{};
    unsigned i = 0;
    for (const auto &p : pairs) {
        result[i++] = {p.address + 2, 0xffa0, std::uint16_t(0xffa0 + border)};
        result[i++] = {p.address + 6, p.limit, std::uint16_t(p.limit + border * 2)};
    }
    return result;
}
inline constexpr auto sh1_sites = make_sites(sh1_pairs);
inline constexpr auto sh2_sites = make_sites(sh2_pairs);
inline const std::array<immediate_site, 36> &sites(profile game)
{
    return game == profile::sh2 ? sh2_sites : sh1_sites;
}

// The caller must authenticate the original cartridge and validate all sites
// before installing read taps. Read returns big-endian guest words from the
// restored ROM, before any viewport read substitution. The taps can then return
// `wide` only while the option is active, without mutating the ROM or save state.
template<class Read> bool validate(Read read, profile game)
{
    const auto &pairs = game == profile::sh2 ? sh2_pairs : sh1_pairs;
    for (const auto &p : pairs) {
        if (read(p.address) != p.offset_opcode ||
            read(p.address + 4) != p.limit_opcode ||
            read(p.address + 2) != 0xffa0 || read(p.address + 6) != p.limit)
            return false;
    }
    return true;
}

struct lifetime_pair {
    std::uint32_t address;
    std::uint16_t add_opcode, branch_opcode;
};

// These handlers project X relative to the camera centre, then remove an
// object when unsigned(projected_x + 196) > 392. Preserve the original
// 36-pixel margin around the wider viewport: [-36,356] becomes [-89,409].
// Rejection leads to object unlink/free, sometimes also decrementing an actor
// count. Extending lifetime can therefore change pool occupancy or phase end
// timing in this optional mode. No collision/score arithmetic is replaced.
inline constexpr std::array<lifetime_pair, 38> sh1_lifetime_pairs{{
    {0x12551e, 0x0641, 0x626e},
    {0x12c624, 0x0641, 0x6200},
    {0x12c73c, 0x0641, 0x6300},
    {0x12c868, 0x0641, 0x6300},
    {0x12c93a, 0x0641, 0x6300},
    {0x12cac8, 0x0641, 0x6200},
    {0x12cbba, 0x0641, 0x6300},
    {0x12cd92, 0x0641, 0x6300},
    {0x12ce64, 0x0641, 0x6300},
    {0x12d032, 0x0641, 0x6220},
    {0x12d18a, 0x0641, 0x6300},
    {0x12d25c, 0x0641, 0x6300},
    {0x12d32e, 0x0641, 0x6300},
    {0x12d400, 0x0641, 0x6300},
    {0x12d4d2, 0x0641, 0x6300},
    {0x12d5a4, 0x0641, 0x6300},
    {0x12d676, 0x0641, 0x6300},
    {0x12d748, 0x0641, 0x6300},
    {0x12d81a, 0x0641, 0x6300},
    {0x12d8ec, 0x0641, 0x6300},
    {0x16f096, 0x0640, 0x6264},
    {0x16f0fa, 0x0640, 0x639c},
    {0x16f2dc, 0x0640, 0x6200},
    {0x19a284, 0x0640, 0x6200},
    {0x19a330, 0x0640, 0x6300},
    {0x19a43a, 0x0641, 0x6200},
    {0x19a520, 0x0641, 0x6300},
    {0x1d7566, 0x0641, 0x621e},
    {0x1d76d2, 0x0641, 0x6300},
    {0x1d77a4, 0x0641, 0x6300},
    {0x1d7876, 0x0641, 0x6300},
    {0x1d7948, 0x0641, 0x6300},
    {0x1d7a1a, 0x0641, 0x6300},
    {0x1d7aec, 0x0641, 0x6300},
    {0x1d7bbe, 0x0641, 0x6300},
    {0x1d7c90, 0x0641, 0x6300},
    {0x1d7d62, 0x0641, 0x6300},
    {0x1d7e34, 0x0641, 0x6300},
}};
inline constexpr std::array<lifetime_pair, 8> sh2_lifetime_pairs{{
    {0x0f1640, 0x0640, 0x626a},
    {0x0f16aa, 0x0640, 0x6396},
    {0x137b64, 0x0640, 0x6276},
    {0x137bda, 0x0640, 0x638a},
    {0x137d5a, 0x0640, 0x6200},
    {0x137df2, 0x0640, 0x6300},
    {0x137f74, 0x0640, 0x6200},
    {0x13800c, 0x0640, 0x6300},
}};

template<std::size_t N>
constexpr std::array<immediate_site, N * 2> make_lifetime_sites(const std::array<lifetime_pair, N> &pairs)
{
    std::array<immediate_site, N * 2> result{};
    unsigned i = 0;
    for (const auto &p : pairs) {
        result[i++] = {p.address + 2, 196, std::uint16_t(196 + border)};
        result[i++] = {p.address + 6, 392, std::uint16_t(392 + border * 2)};
    }
    return result;
}
inline constexpr auto sh1_lifetime_sites = make_lifetime_sites(sh1_lifetime_pairs);
inline constexpr auto sh2_lifetime_sites = make_lifetime_sites(sh2_lifetime_pairs);

struct site_view {
    const immediate_site *data;
    std::size_t count;
    const immediate_site *begin() const { return data; }
    const immediate_site *end() const { return data + count; }
    std::size_t size() const { return count; }
};
inline site_view lifetime_sites(profile game)
{
    return game == profile::sh2 ? site_view{sh2_lifetime_sites.data(), sh2_lifetime_sites.size()} :
                                 site_view{sh1_lifetime_sites.data(), sh1_lifetime_sites.size()};
}

template<class Read, std::size_t N>
bool validate_lifetime_pairs(Read read, const std::array<lifetime_pair, N> &pairs)
{
    for (const auto &p : pairs) {
        if (read(p.address) != p.add_opcode || read(p.address + 2) != 196 ||
            read(p.address + 4) != 0x0c40 + (p.add_opcode & 7) ||
            read(p.address + 6) != 392 || read(p.address + 8) != p.branch_opcode)
            return false;
    }
    return true;
}
template<class Read> bool validate_lifetimes(Read read, profile game)
{
    return game == profile::sh2 ? validate_lifetime_pairs(read, sh2_lifetime_pairs) :
                                 validate_lifetime_pairs(read, sh1_lifetime_pairs);
}

// The native screen-space projectile handlers have a separate unsigned
// X-in-[0,320] guard. Merely increasing 320 would still delete a projectile at
// X=-1. Replace the six-byte CMP/BHI pair by a JMP to a comparison trampoline.
// 3FF000 is inside the cartridge bus mapping, outside both authenticated ROM
// images and the SH1-art injection range. Read taps supply these new words;
// underlying cartridge bytes (including mirrored ROM banks) are not changed.
inline constexpr std::uint32_t projectile_stub_address = 0x3ff000;
inline constexpr std::array<immediate_site, 3> sh1_projectile_jump{{
    {0x199bf4, 0x0c40, 0x4ef9},
    {0x199bf6, 0x0140, 0x003f},
    {0x199bf8, 0x6234, 0xf000},
}};
inline constexpr std::array<immediate_site, 3> sh2_projectile_jump{{
    {0x16ee6a, 0x0c40, 0x4ef9},
    {0x16ee6c, 0x0140, 0x003f},
    {0x16ee6e, 0x623e, 0xf000},
}};
inline const std::array<immediate_site, 3> &projectile_jump_sites(profile game)
{
    return game == profile::sh2 ? sh2_projectile_jump : sh1_projectile_jump;
}

constexpr std::array<std::uint16_t, 17> make_projectile_stub(std::uint32_t keep, std::uint32_t remove)
{
    return {{
        0x48e7, 0x2040,             // MOVEM.L D2/A1,-(A7)
        0x3240,                     // MOVEA.W D0,A1 (sign extends, preserves X)
        0x43e9, border,             // LEA 53(A1),A1 (preserves X)
        0x3409,                     // MOVE.W A1,D2
        0x0c42, 320 + border * 2,   // CMPI.W #426,D2
        0x4cdf, 0x0204,             // MOVEM.L (A7)+,D2/A1 (preserves comparison)
        0x6206,                     // BHI remove
        0x4ef9, std::uint16_t(keep >> 16), std::uint16_t(keep),
        0x4ef9, std::uint16_t(remove >> 16), std::uint16_t(remove),
    }};
}
inline constexpr auto sh1_projectile_stub = make_projectile_stub(0x199bfa, 0x199c2e);
inline constexpr auto sh2_projectile_stub = make_projectile_stub(0x16ee70, 0x16eeae);
inline const std::array<std::uint16_t, 17> &projectile_stub_words(profile game)
{
    return game == profile::sh2 ? sh2_projectile_stub : sh1_projectile_stub;
}

// Validate the overwritten pair, the unchanged Y guard and the native removal
// counter. Install the stub read tap permanently for the authenticated game,
// even in 4:3: an in-progress or restored PC inside it must be able to finish.
// Only the three jump-site substitutions depend on the widescreen preference.
template<class Read> bool validate_projectiles(Read read, profile game)
{
    for (const auto &s : projectile_jump_sites(game))
        if (read(s.address) != s.original) return false;
    const std::uint32_t keep = game == profile::sh2 ? 0x16ee70 : 0x199bfa;
    const std::uint32_t remove = game == profile::sh2 ? 0x16eeae : 0x199c2e;
    return read(keep) == 0x0c41 && read(keep + 2) == 210 &&
           read(keep + 4) == (game == profile::sh2 ? 0x6238 : 0x622e) &&
           read(remove) == 0x5339 && read(remove + 2) == 0xff &&
           read(remove + 4) == (game == profile::sh2 ? 0x38a6 : 0x40a6);
}

} // namespace sh_widescreen
