// license:GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace sh1_player_motion {

// Leave room for two presentation phases and their endpoint in unsigned math.
inline constexpr std::uint32_t max_interval =
    (std::numeric_limits<std::uint32_t>::max() - 2U) / 2U;

inline bool valid_owner(std::uint32_t owner)
{
    return owner >= 0xff0000 && owner <= 0xffffb4 && !(owner & 1);
}

inline bool valid_coordinate(std::int32_t coordinate)
{
    return coordinate >= -32768 && coordinate <= 32767;
}

struct history {
    std::uint32_t owner = 0, tick = 0, age = 0, span = 1;
    std::int32_t x[2]{}, y[2]{};
    bool valid = false;

    void clear() { *this = history{}; }

    // The completed native game-loop counter advances even when Harrier holds
    // still. Ignore live coordinates until that counter changes: another game
    // loop may already have started writing the next position into guest RAM.
    void sample(std::uint32_t player, std::uint32_t completed_tick,
                std::int32_t live_x, std::int32_t live_y)
    {
        if (!valid_owner(player)) { clear(); return; }
        if (!valid || owner != player) {
            clear();
            if (!valid_coordinate(live_x) || !valid_coordinate(live_y)) return;
            owner = player; tick = completed_tick;
            x[0] = x[1] = live_x; y[0] = y[1] = live_y;
            valid = true;
            return;
        }
        if (age < max_interval) ++age;
        else age = max_interval;
        if (completed_tick == tick) return;
        if (!valid_coordinate(live_x) || !valid_coordinate(live_y)) { clear(); return; }
        x[0] = x[1]; y[0] = y[1];
        x[1] = live_x; y[1] = live_y;
        tick = completed_tick;
        span = std::max(1U, age);
        age = 0;
    }
};

inline history state;

// Explicit bytes, independent of C++ object layout, bool size and host endian.
// This optional footer can be absent from older libretro save states.
inline constexpr std::size_t state_size = 64;

namespace detail {

inline bool valid_history(const history &h)
{
    if (!h.valid)
        return h.owner == 0 && h.tick == 0 && h.age == 0 && h.span == 1 &&
            h.x[0] == 0 && h.x[1] == 0 && h.y[0] == 0 && h.y[1] == 0;
    return valid_owner(h.owner) && h.age <= max_interval &&
        h.span >= 1 && h.span <= max_interval &&
        valid_coordinate(h.x[0]) && valid_coordinate(h.x[1]) &&
        valid_coordinate(h.y[0]) && valid_coordinate(h.y[1]);
}

inline void write32(std::uint8_t *bytes, std::uint32_t value)
{
    for (unsigned i = 0; i < 4; ++i) bytes[i] = std::uint8_t(value >> (24 - i * 8));
}

inline std::uint32_t read32(const std::uint8_t *bytes)
{
    return (std::uint32_t(bytes[0]) << 24) | (std::uint32_t(bytes[1]) << 16) |
        (std::uint32_t(bytes[2]) << 8) | bytes[3];
}

inline std::int32_t signed32(std::uint32_t value)
{
    if (value <= std::uint32_t(std::numeric_limits<std::int32_t>::max()))
        return std::int32_t(value);
    return -1 - std::int32_t(std::numeric_limits<std::uint32_t>::max() - value);
}

inline std::uint32_t checksum(const std::uint8_t *bytes)
{
    std::uint32_t hash = 2166136261U;
    for (std::size_t i = 0; i < state_size; ++i) {
        if (i >= 56 && i < 60) continue; // Exclude the checksum field itself.
        hash = (hash ^ bytes[i]) * 16777619U;
    }
    return hash;
}

inline constexpr std::array<std::uint8_t, 8> magic{{'S','H','1','P','M','O','T',0}};
inline constexpr std::uint32_t version = 1, end_tag = 0x454e4421; // "END!"

} // namespace detail

inline bool encode(void *destination, std::size_t size, const history &h)
{
    if (!destination || size != state_size || !detail::valid_history(h)) return false;
    std::array<std::uint8_t, state_size> bytes{};
    std::copy(detail::magic.begin(), detail::magic.end(), bytes.begin());
    detail::write32(bytes.data() + 8, detail::version);
    detail::write32(bytes.data() + 12, std::uint32_t(state_size));
    detail::write32(bytes.data() + 16, h.owner);
    detail::write32(bytes.data() + 20, h.tick);
    detail::write32(bytes.data() + 24, h.age);
    detail::write32(bytes.data() + 28, h.span);
    detail::write32(bytes.data() + 32, std::uint32_t(h.x[0]));
    detail::write32(bytes.data() + 36, std::uint32_t(h.x[1]));
    detail::write32(bytes.data() + 40, std::uint32_t(h.y[0]));
    detail::write32(bytes.data() + 44, std::uint32_t(h.y[1]));
    detail::write32(bytes.data() + 48, h.valid ? 1U : 0U);
    // Reserved word at 52 is zero; future formats require a new version.
    detail::write32(bytes.data() + 60, detail::end_tag);
    detail::write32(bytes.data() + 56, detail::checksum(bytes.data()));
    std::memcpy(destination, bytes.data(), bytes.size());
    return true;
}

inline bool decode(const void *source, std::size_t size, history &out)
{
    if (!source || size != state_size) return false;
    const auto *bytes = static_cast<const std::uint8_t *>(source);
    if (!std::equal(detail::magic.begin(), detail::magic.end(), bytes) ||
        detail::read32(bytes + 8) != detail::version ||
        detail::read32(bytes + 12) != state_size ||
        detail::read32(bytes + 48) > 1 || detail::read32(bytes + 52) != 0 ||
        detail::read32(bytes + 60) != detail::end_tag ||
        detail::read32(bytes + 56) != detail::checksum(bytes)) return false;
    history candidate;
    candidate.owner = detail::read32(bytes + 16);
    candidate.tick = detail::read32(bytes + 20);
    candidate.age = detail::read32(bytes + 24);
    candidate.span = detail::read32(bytes + 28);
    candidate.x[0] = detail::signed32(detail::read32(bytes + 32));
    candidate.x[1] = detail::signed32(detail::read32(bytes + 36));
    candidate.y[0] = detail::signed32(detail::read32(bytes + 40));
    candidate.y[1] = detail::signed32(detail::read32(bytes + 44));
    candidate.valid = detail::read32(bytes + 48) != 0;
    if (!detail::valid_history(candidate)) return false;
    out = candidate;
    return true;
}

} // namespace sh1_player_motion
