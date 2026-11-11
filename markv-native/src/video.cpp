#include "video.hpp"
#include "interpolation.hpp"

#include <algorithm>
#include <bit>

namespace markv {
namespace {

constexpr unsigned priority = 0x80;

unsigned horizontal_size(const Video &video)
{
    return (video.reg[12] & 0x81) == 0x81 ? 320 : 256;
}

unsigned plane_base(const Video &video, unsigned plane)
{
    if (plane == 0)
        return (video.reg[2] & 0x38) * 512;
    return (video.reg[4] & 7) * 4096;
}

std::uint32_t pattern(const Video &video, Word descriptor, unsigned y,
                      unsigned tile_height, unsigned bank, unsigned address_mask)
{
    if (descriptor & 0x1000)
        y ^= tile_height - 1;
    const unsigned tile = descriptor & (tile_height == 8 ? 2047 : 1023);
    const unsigned address = bank | (tile * tile_height * 2 + y * 2);
    return (std::uint32_t(video.vram[address & address_mask]) << 16) |
           video.vram[(address + 1) & address_mask];
}

Byte nibble(std::uint32_t row, unsigned x)
{
    return (row >> (28 - x * 4)) & 15;
}

Word packed_color(Byte red, Byte green, Byte blue)
{
    return Word(red | (green << 3) | (blue << 6));
}

constexpr auto rgb444_palette()
{
    std::array<Pixel, 512> table{};
    for (unsigned i = 0; i < table.size(); ++i)
        table[i] = (((i & 7) << 16) | (((i >> 3) & 7) << 8) | (i >> 6)) * 17;
    return table;
}

constexpr auto dark_colors = rgb444_palette();

} // namespace

void Video::set_color(unsigned index, Word color)
{
    cram[index] = color;
    const unsigned code = packed_color((color >> 1) & 7, (color >> 5) & 7, (color >> 9) & 7);
    palette[index] = dark_colors[code];
    palette[index + 128] = dark_colors[code] * 2;
}

void Renderer::draw_sprite(const Video &video, const SpritePiece &sprite, unsigned source_y,
                           unsigned cells, bool scaled, bool mark_vi)
{
    constexpr Byte sample[8][8] = {
        {}, {4}, {2, 6}, {1, 4, 6}, {1, 3, 5, 7}, {0, 2, 4, 5, 7},
        {0, 2, 3, 4, 6, 7}, {0, 1, 2, 4, 5, 6, 7},
    };
    const unsigned rows = ((sprite.shape >> 8) & 3) + 1;
    const unsigned columns = ((sprite.shape >> 10) & 3) + 1;
    const unsigned tile_y = (sprite.descriptor & 0x1000) ? rows - 1 - source_y / 8 : source_y / 8;
    Word descriptor = sprite.descriptor + tile_y;
    const bool reverse = descriptor & 0x0800;
    const unsigned bank = scaled ? (sprite.shape & 0x3000) << 3 : 0;
    const unsigned palette_bank = (scaled && (sprite.shape & 0x4000)) ? 64 : 0;

    // Draw the linked order front to back. Transparent pixels leave the next
    // piece eligible, regardless of which list supplied it.
    for (unsigned cell = 0; cell < cells; ++cell, descriptor += rows) {
        const unsigned column = reverse ? columns - 1 - cell : cell;
        const int left = sprite.x + int(column * sprite.x_step / 8);
        const int right = sprite.x + int((column + 1) * sprite.x_step / 8);
        const unsigned length = right - left;
        if (!length || right <= -padding || left >= viewport + padding ||
            (!padding && !mark_vi && left < 0 && length < 8))
            continue;
        const auto row = pattern(video, descriptor, source_y & 7, 8, bank, 65535);
        const unsigned attributes = ((descriptor >> 9) & 48) | palette_bank |
                                    ((descriptor & 0x8000) ? priority : 0);
        const unsigned flip = (descriptor & 0x0800) ? 7 : 0;
        const bool exclude_center = !mark_vi && left < 0 && length < 8;
        for (int x = std::max(left, -padding); x < std::min(right, viewport + padding); ++x) {
            if (exclude_center && x >= 0 && x < viewport)
                continue;
            const unsigned within = x - left;
            const unsigned source = length == 8 ? within : sample[length][within];
            const unsigned color = nibble(row, source ^ flip);
            Byte &pixel = sprite_pixels[x + padding];
            if (color && !pixel)
                pixel = Byte(attributes | color);
        }
    }
}

void Renderer::sprites(const Video &video, unsigned y, bool mark_vi, SpriteList objects,
                       const NativeMidpoints *motion)
{
    const bool scaled = video.reg[36] & 128;
    std::fill_n(sprite_pixels.begin(), screen_width + 2 * padding, 0);
    if (mark_vi && objects.active) {
        for (const auto &piece : objects.pieces) {
            const unsigned rows = ((piece.shape >> 8) & 3) + 1;
            const unsigned relative = (y + 128 - piece.y) & 1023;
            const unsigned y_step = scaled ? piece.y_step : 64;
            if (relative >= rows * y_step / 8)
                continue;
            auto sprite = piece;
            if (!scaled)
                sprite.x_step = 64;
            draw_sprite(video, sprite, relative * 64 / y_step, ((piece.shape >> 10) & 3) + 1,
                        scaled, true);
        }
        return;
    }

    unsigned sprites_left = viewport / 16;
    unsigned columns_left = viewport / 8;
    const unsigned table = (video.reg[5] & 127) * 256;
    if (motion && motion->table != table)
        motion = nullptr;
    const unsigned transforms = (video.reg[36] & 31) * 2048;
    std::array<std::uint64_t, 2> visited{};
    unsigned entry = 0;
    SpritePiece pending{};
    unsigned pending_columns = 0, pending_y = 0;
    do {
        visited[entry >> 6] |= std::uint64_t{1} << (entry & 63);
        const unsigned offset = table | (entry * 4);
        Word top = video.vram[offset];
        const Word shape = video.vram[offset + 1];
        const Word position = video.vram[offset + 3];
        const unsigned zoom = transforms + (position >> 9) * 8;
        unsigned y_step = scaled ? (video.vram[zoom + 3] & 32767) / 64 : 64;
        const SpritePiece *midpoint = nullptr;
        if (motion && motion->moving[entry]) {
            const auto &candidate = motion->entries[entry];
            if (candidate.y == top && candidate.shape == shape && candidate.position == position &&
                candidate.descriptor == video.vram[offset + 2] && candidate.y_step == y_step &&
                candidate.x_step == (scaled ? std::min(4096u, video.vram[zoom] & 32767u) / 64 : 64)) {
                midpoint = &candidate.midpoint;
                top = midpoint->y;
                y_step = midpoint->y_step;
            }
        }
        const unsigned relative = (y + 128 - top) & 1023;
        if (relative < (((shape >> 8) & 3) + 1) * y_step / 8) {
            if (!(position & 511))
                break;
            const unsigned x_step = midpoint ? midpoint->x_step :
                scaled ? std::min(4096u, video.vram[zoom] & 32767u) / 64 : 64;
            const unsigned columns = ((shape >> 10) & 3) + 1;
            const int x = midpoint ? midpoint->x : int(position & 511) - 128;
            const SpritePiece piece{x, top, shape, video.vram[offset + 2], x_step, y_step};
            const unsigned source_y = scaled ? relative * 64 / y_step : relative;
            if (mark_vi) {
                draw_sprite(video, piece, source_y, columns, scaled, true);
            } else {
                if (pending_columns)
                    draw_sprite(video, pending, pending_y, pending_columns, scaled, false);
                pending = piece;
                pending_y = source_y;
                pending_columns = columns;
                if (!--sprites_left || columns_left <= columns)
                    break;
                columns_left -= columns;
            }
        }
        entry = shape & 127;
    } while (!(visited[entry >> 6] & (std::uint64_t{1} << (entry & 63))));

    // The last native sprite sees the residual tile-column budget.
    if (pending_columns)
        draw_sprite(video, pending, pending_y, std::min(columns_left, pending_columns), scaled, false);
}

void Renderer::tile_row(Word descriptor, std::uint32_t row, unsigned source_x,
                        int begin, int end, bool plane_b)
{
    begin += padding;
    end += padding;
    const unsigned flip = (descriptor & 0x0800) ? 7 : 0;
    const Byte palette_index = (descriptor >> 9) & 48;
    if (descriptor & 0x8000) {
        for (int x = begin; x < end; ++x, ++source_x) {
            const Byte color = nibble(row, source_x ^ flip);
            if (color || plane_b)
                foreground[x] = palette_index | color | priority;
            else
                foreground[x] |= priority;
        }
        return;
    }
    for (int x = begin; x < end; ++x, ++source_x) {
        const Byte color = nibble(row, source_x ^ flip);
        if (color)
            background[x] = palette_index | color;
    }
}

void Renderer::tiled(const Video &video, unsigned y, unsigned plane, int begin,
                     int end, bool interlace, bool window_edge)
{
    constexpr unsigned columns_by_mode[] = {32, 64, 64, 128};
    constexpr unsigned rows_by_mode[][4] = {
        {32, 64, 64, 128}, {32, 64, 64, 64}, {1, 1, 1, 1}, {32, 32, 64, 128},
    };
    const unsigned horizontal_mode = video.reg[16] & 3;
    const unsigned vertical_mode = (video.reg[16] >> 4) & 3;
    const unsigned columns = columns_by_mode[horizontal_mode];
    const unsigned tile_height = interlace ? 16 : 8;
    const unsigned height_mask = rows_by_mode[horizontal_mode][vertical_mode] * tile_height - 1;
    const unsigned scroll_mode = video.reg[11] & 3;
    const bool scroll_by_column = video.reg[11] & 4;
    const unsigned line = interlace ? y / 2 : y;
    constexpr unsigned line_mask[] = {0, 7, ~7u, ~0u};
    const unsigned scroll_address = (video.reg[13] & 63) * 512 + (line & line_mask[scroll_mode]) * 2;
    const unsigned scroll = video.vram[(scroll_address + plane) & 32767];
    const unsigned base = plane_base(video, plane);

    for (int x = begin; x < end;) {
        const int block = x >> 4;
        const unsigned within = unsigned(x) & 15;
        const unsigned shift = scroll & 7;
        const unsigned cell = (within + 8 - shift) / 8;
        const unsigned tile_x = (block * 2 + cell - 1 - scroll / 8) & (columns - 1);
        const unsigned source_x = (within - shift) & 7;
        const int last = std::min({end, x + 8 - int(source_x), (block + 1) * 16});
        const unsigned vcolumn = (cell < 2 && (scroll & 15)) ? block - 1 : block;
        const unsigned vertical = video.vscroll[scroll_by_column ? (vcolumn * 2 + plane) & 63 : plane];
        const unsigned source_y = (y + vertical) & height_mask;
        const bool window_quirk = window_edge && block == (begin >> 4) &&
                                  (scroll & 15) && (cell == 0 || (cell == 1 && (scroll & 8)));
        const unsigned column = (tile_x + (window_quirk ? 2 : 0)) & (columns - 1);
        const Word descriptor = video.vram[(base + (source_y / tile_height) * columns + column) & 32767];
        tile_row(descriptor, pattern(video, descriptor, source_y & (tile_height - 1),
                                     tile_height, 0, 32767),
                 source_x, x, last, plane == 1);
        x = last;
    }
}

void Renderer::window(const Video &video, unsigned y, unsigned begin, unsigned end,
                      unsigned viewport, bool interlace)
{
    const unsigned columns = viewport == 320 ? 64 : 32;
    const unsigned tile_height = interlace ? 16 : 8;
    const unsigned base = ((video.reg[3] >> 1) & (columns == 64 ? 30 : 31)) * 1024;
    const unsigned row = base + ((y & 255) / tile_height) * columns;
    for (unsigned x = begin; x < end;) {
        const unsigned last = std::min(end, (x | 7) + 1);
        const Word descriptor = video.vram[(row + ((x / 8) & (columns - 1))) & 32767];
        tile_row(descriptor, pattern(video, descriptor, y & (tile_height - 1), tile_height, 0, 32767),
                 x & 7, x, last, false);
        x = last;
    }
}

void Renderer::affine(const Video &video, unsigned y, unsigned plane, int begin, int end, int line_origin)
{
    const unsigned control = video.reg[32 + plane];
    const bool per_line = control & 32;
    const bool wrap = control & 64;
    const auto *entry = &video.vram[(control & 31) * 2048 + (per_line ? y * 8 : 0)];
    const int dx = std::bit_cast<std::int16_t>(entry[0]);
    const int dy = std::bit_cast<std::int16_t>(entry[1]);
    std::uint32_t fx = (std::uint32_t(entry[4]) << 16) | entry[5];
    std::uint32_t fy = (std::uint32_t(entry[6]) << 16) | entry[7];
    if (per_line) {
        fx += std::uint32_t((begin - line_origin) * dx);
        fy += std::uint32_t((begin - line_origin) * dy);
    } else {
        fx += std::uint32_t(int(y) * std::bit_cast<std::int16_t>(entry[2]) + int(begin) * dx);
        fy += std::uint32_t(int(y) * std::bit_cast<std::int16_t>(entry[3]) + int(begin) * dy);
    }
    constexpr unsigned column_bits[] = {5, 6, 0, 7};
    const unsigned columns = column_bits[video.reg[16] & 3];
    const int x_limit = (8 << columns) - 1;
    const int y_limit = (8 << column_bits[(video.reg[16] >> 4) & 3]) - 1;
    const unsigned base = plane_base(video, plane);
    const auto draw = [&]<bool Wrap>() {
        unsigned previous_key = ~0u;
        Word descriptor = 0;
        std::uint32_t pixels = 0;
        for (int x = begin + padding; x < end + padding; ++x, fx += dx, fy += dy) {
            int tx = std::bit_cast<std::int32_t>(fx) >> 12;
            int ty = std::bit_cast<std::int32_t>(fy) >> 12;
            if constexpr (Wrap) {
                tx &= x_limit;
                ty &= y_limit;
            } else {
                tx = std::clamp(tx, 0, x_limit);
                ty = std::clamp(ty, 0, y_limit);
            }
            const unsigned address = (base | ((unsigned(ty) / 8) << columns) | (unsigned(tx) / 8)) & 65535;
            const unsigned key = address * 8 + (ty & 7);
            if (key != previous_key) {
                descriptor = video.vram[address];
                pixels = pattern(video, descriptor, ty & 7, 8, 0, 65535);
                previous_key = key;
            }
            const unsigned flip = (descriptor & 0x0800) ? 7 : 0;
            const Byte color = nibble(pixels, (tx & 7) ^ flip);
            const Byte palette_index = (descriptor >> 9) & 48;
            if (descriptor & 0x8000) {
                if (color)
                    foreground[x] = palette_index | color | priority;
                else
                    foreground[x] |= priority;
            } else if (color) {
                background[x] = palette_index | color;
            }
        }
    };
    if (wrap)
        draw.template operator()<true>();
    else
        draw.template operator()<false>();
}

void Renderer::planes(const Video &video, unsigned y, bool interlace)
{
    const unsigned boundary = std::min<unsigned>(viewport, (video.reg[17] & 31) * 16);
    const unsigned y_boundary = std::min<unsigned>((video.reg[1] & 8) ? 240 : 224,
                                                   (video.reg[18] & 31) * 8);
    const bool right = video.reg[17] & 128;
    const bool full_window = (video.reg[18] & 128) ? y >= y_boundary : y < y_boundary;

    if (video.reg[33] & 128)
        affine(video, y, 1, -padding, viewport + padding, 0);
    else
        tiled(video, y, 1, -padding, viewport + padding, interlace, false);

    const int plane_a_begin = right ? 0 : int(boundary);
    if (padding && !full_window && boundary != (right ? 0u : unsigned(viewport))) {
        for (const int edge : {-padding, viewport}) {
            if ((edge < 0 && plane_a_begin != 0) || (edge >= 0 && right && boundary != unsigned(viewport)))
                continue;
            const int end = edge + padding;
            if (video.reg[32] & 128)
                affine(video, y, 0, edge, end, plane_a_begin);
            else
                tiled(video, y, 0, edge, end, interlace, false);
        }
    }
    if (full_window) {
        window(video, y, 0, viewport, viewport, interlace);
        return;
    }
    window(video, y, right ? boundary : 0, right ? viewport : boundary, viewport, interlace);
    const int begin = plane_a_begin;
    const unsigned end = right ? boundary : viewport;
    if (video.reg[32] & 128)
        affine(video, y, 0, begin, end, begin);
    else
        tiled(video, y, 0, begin, end, interlace, !right && boundary != 0);
}

template<bool Shadow>
void Renderer::composite(const Video &video, std::span<Pixel> output) const
{
    for (unsigned x = 0; x < output.size(); ++x) {
        const unsigned upper = foreground[x];
        const bool priority_plane = upper & 15;
        unsigned index = priority_plane ? upper : background[x] | (upper & priority);
        const unsigned sprite = sprite_pixels[x];
        const bool sprite_visible = sprite && ((sprite & priority) || !priority_plane);
        if constexpr (Shadow) {
            if (sprite_visible) {
                if ((sprite & 62) == 62)
                    index = (sprite & 1) ? index & 127 : index ^ 128;
                else
                    index = sprite | (index & priority);
            }
        } else {
            index = (sprite_visible ? sprite : index) | 128;
        }
        output[x] = video.palette[index];
    }
}

void Renderer::render(const Video &video, unsigned y, bool interlace, std::span<Pixel> output,
                      bool mark_vi, SpriteList objects, IntermediateScanline intermediate)
{
    viewport = horizontal_size(video);
    const bool wide = output.size() == wide_width;
    padding = wide ? wide_border : 0;
    const unsigned backdrop = video.reg[7] & 127;
    const auto blank_color = video.palette[backdrop | 128];
    if (wide && viewport != int(screen_width)) {
        // A 256-column mode occupies the original central area.
        std::fill(output.begin(), output.end(), blank_color);
        if (!intermediate.output.empty()) {
            std::fill(intermediate.output.begin(), intermediate.output.end(), blank_color);
            intermediate.output = intermediate.output.subspan(wide_border, screen_width);
        }
        render(video, y, interlace, output.subspan(wide_border, screen_width), mark_vi, objects, intermediate);
        return;
    }
    if (!(video.reg[1] & 64) || (video.reg[0] & 1)) {
        sprites(video, y, mark_vi, objects, nullptr);
        std::fill(output.begin(), output.end(), blank_color);
        std::fill(intermediate.output.begin(), intermediate.output.end(), blank_color);
        return;
    }

    std::fill_n(foreground.begin(), output.size(), 0);
    std::fill_n(background.begin(), output.size(), Byte(backdrop));
    planes(video, y, interlace);
    const auto compose = [&](std::span<Pixel> pixels) {
        if (video.reg[12] & 8)
            composite<true>(video, pixels);
        else
            composite<false>(video, pixels);
    };

    // Both presentations use these planes. Draw the native sprites last so
    // captured_sprite() continues to report the emulated hardware output.
    const bool moving = intermediate.objects.active || (!objects.active && intermediate.motion);
    if (moving) {
        sprites(video, y, mark_vi, intermediate.objects.active ? intermediate.objects : objects, intermediate.motion);
        compose(intermediate.output);
    }
    sprites(video, y, mark_vi, objects, nullptr);
    compose(output);
    if (!moving && !intermediate.output.empty())
        std::copy(output.begin(), output.end(), intermediate.output.begin());
}

Word Renderer::captured_sprite(unsigned x) const
{
    const unsigned sprite = sprite_pixels[x + padding];
    if (!sprite)
        return 0;
    return (sprite & 63) | ((sprite & 64) << 2) | ((sprite & 128) ? 128 : 64);
}

} // namespace markv
