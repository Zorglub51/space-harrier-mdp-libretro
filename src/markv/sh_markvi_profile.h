// license:GPL-2.0-or-later
#pragma once
#include <cstdint>

namespace sh_markvi {
// Authenticated native producer layouts. These addresses identify actual
// constructor banks; they do not impose host object or sprite budgets.
struct producer {
    std::uint32_t selector, head_pointer, second_head;
    std::uint32_t tail[2], tail_count[2];
};
inline constexpr producer sh1_producer{
    0xff1be0, 0xff1210, 0xff1ec8,
    {0xff16dc, 0xff195e}, {0xff195c, 0xff1bde}
};
inline constexpr producer sh2_producer{
    0xff387c, 0xff0e00, 0xff3080,
    {0xff118a, 0xff140c}, {0xff140a, 0xff168c}
};
inline const producer &layout(unsigned game)
{
    return game == 1 ? sh1_producer : sh2_producer;
}
} // namespace sh_markvi
