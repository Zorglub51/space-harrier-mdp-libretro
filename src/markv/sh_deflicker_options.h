// license:GPL-2.0-or-later
#pragma once

#include <atomic>
#include <cstdint>
#include <cstring>

namespace sh_mdp_deflicker {

// These are frontend preferences, not emulated state. The game keeps its own
// byte in RAM; an explicit preference overrides only reads of that byte.
inline std::atomic<int> sh1{-1}, sh2{-1};
inline constexpr std::uint32_t sh1_address = 0xff3c36;
inline constexpr std::uint32_t sh2_address = 0xff2e62;

inline int parse(const char *value)
{
    if (value && !std::strcmp(value, "off")) return 0;
    if (value && !std::strcmp(value, "on1")) return 1;
    if (value && !std::strcmp(value, "on2")) return 2;
    return -1;
}

inline std::uint16_t read(std::uint16_t data, std::uint16_t mask, int mode)
{
    // Both settings occupy the high byte of a big-endian 68000 word.
    // Preserve the adjacent byte, partial accesses and all unforced reads.
    if (mode >= 0 && mode <= 2 && (mask & 0xff00))
        data = (data & ~std::uint16_t(mask & 0xff00)) |
            ((std::uint16_t(mode) << 8) & mask);
    return data;
}

} // namespace sh_mdp_deflicker
