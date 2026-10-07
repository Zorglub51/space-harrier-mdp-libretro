// license:GPL-2.0-or-later
#include "sh2_markvi.h"
#include <algorithm>
#include <cstddef>
#include <cstring>

extern "C" std::size_t markvi_build(const unsigned char *rom, std::size_t rom_size,
                                   const unsigned char *ram, unsigned short *result,
                                   std::size_t capacity)
{
    bool valid = true;
    auto read = [&](std::uint32_t p) -> std::uint16_t {
        const unsigned char *bytes = nullptr;
        if (p >= 0xfe0000 && p <= 0xfffffe) bytes = ram + p - 0xfe0000;
        else if (p + 1 < rom_size) bytes = rom + p;
        else { valid = false; return 0; }
        return (std::uint16_t(bytes[0]) << 8) | bytes[1];
    };
    std::vector<sh2_markvi::sprite> sprites;
    if (!sh2_markvi::build(read, sprites) || !valid) return std::size_t(-1);
    if (capacity >= sprites.size())
        for (std::size_t i = 0; i < sprites.size(); ++i) {
            const auto &s = sprites[i];
            const unsigned short fields[] = {s.y, s.size, s.attr, s.x, s.zoom};
            std::copy_n(fields, 5, result + i * 5);
        }
    return sprites.size();
}
