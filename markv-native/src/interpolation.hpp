#pragma once

#include "video.hpp"

#include <bitset>
#include <vector>

namespace markv {

struct NativeMidpoints {
    struct Entry {
        Word y, shape, descriptor, position;
        unsigned x_step, y_step;
        SpritePiece midpoint;
    };
    std::array<Entry, 128> entries{};
    std::bitset<128> moving;
    unsigned table = 0;
};

class FrameInterpolation {
public:
    void begin(const Video &video, SpriteList objects, unsigned width, bool mark_vi);
    void reset() { previous_width = 0; }

    std::span<Pixel> line(unsigned y, unsigned width) { return {pixels.data() + y * width, width}; }
    std::span<const Pixel> frame(unsigned width) const { return {pixels.data(), width * screen_height}; }
    SpriteList between_objects(SpriteList objects) const;
    const NativeMidpoints *between_native() const { return native.moving.any() ? &native : nullptr; }

private:
    void match_native(const Video &video, bool continuous);
    void match_objects(SpriteList objects, bool continuous);

    std::array<Pixel, wide_width * screen_height> pixels{};
    NativeMidpoints native;
    std::array<SpritePiece, 128> previous_native{};
    std::bitset<128> previous_links;
    std::vector<SpritePiece> previous_objects, midpoint_objects;
    std::uint64_t generation = 0;
    unsigned previous_width = 0;
    Word previous_mode = 0;
    bool previous_extended = false, previous_mark_vi = false, previous_scaled = false;
    bool objects_move = false;
};

} // namespace markv
