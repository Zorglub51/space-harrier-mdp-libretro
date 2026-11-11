#pragma once

#include <array>
#include <cstdint>
#include <span>

namespace markv {

using Byte = std::uint8_t;
using Word = std::uint16_t;
using Pixel = std::uint32_t;

inline constexpr unsigned screen_width = 320;
inline constexpr unsigned screen_height = 224;
inline constexpr unsigned wide_border = 53;
inline constexpr unsigned wide_width = screen_width + 2 * wide_border;

struct SpritePiece {
    int x;
    Word y, shape, descriptor;
    unsigned x_step, y_step;
    std::uint64_t identity = 0;
};

struct SpriteList {
    bool active = false;
    std::span<const SpritePiece> pieces{};
    std::uint64_t generation = 0;
};

struct NativeMidpoints;

struct IntermediateScanline {
    std::span<Pixel> output{};
    SpriteList objects{};
    const NativeMidpoints *motion = nullptr;
};

struct Video {
    std::array<Word, 65536> vram{};
    std::array<Byte, 64> reg{};
    std::array<Word, 64> vscroll{};
    std::array<Word, 128> cram{};
    std::array<Pixel, 256> palette{};

    void set_color(unsigned index, Word color);
};

class Renderer {
public:
    void render(const Video &video, unsigned y, bool interlace,
                std::span<Pixel> output, bool mark_vi = false, SpriteList objects = {},
                IntermediateScanline intermediate = {});
    Word captured_sprite(unsigned x) const;

private:
    void sprites(const Video &video, unsigned y, bool mark_vi, SpriteList objects,
                 const NativeMidpoints *motion);
    void draw_sprite(const Video &video, const SpritePiece &sprite, unsigned source_y,
                     unsigned cells, bool scaled, bool mark_vi);
    void planes(const Video &video, unsigned y, bool interlace);
    void tiled(const Video &video, unsigned y, unsigned plane, int begin,
               int end, bool interlace, bool window_edge);
    void window(const Video &video, unsigned y, unsigned begin, unsigned end,
                unsigned viewport, bool interlace);
    void affine(const Video &video, unsigned y, unsigned plane, int begin, int end, int line_origin);
    void tile_row(Word descriptor, std::uint32_t pattern, unsigned source_x,
                  int begin, int end, bool plane_b);
    template<bool Shadow>
    void composite(const Video &video, std::span<Pixel> output) const;

    std::array<Byte, wide_width> sprite_pixels{}, foreground{}, background{};
    int padding = 0, viewport = screen_width;
};

} // namespace markv
