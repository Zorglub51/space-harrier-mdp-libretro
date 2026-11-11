#include "interpolation.hpp"

#include <algorithm>
#include <cstdlib>
#include <numeric>

namespace markv {
namespace {

bool interpolate(SpritePiece &piece, const SpritePiece &before)
{
    if ((piece.shape & 0xff00) != (before.shape & 0xff00) || piece.descriptor != before.descriptor ||
        !piece.x_step || !piece.y_step || !before.x_step || !before.y_step)
        return false;

    const int dx = before.x - piece.x;
    const int dy = ((before.y - piece.y + 512) & 1023) - 512;
    // A wrap, scene cut or reused entry is not a movement to interpolate.
    if (std::abs(dx) > 64 || std::abs(dy) > 64 ||
        std::abs(int(piece.y_step) - int(before.y_step)) > 64)
        return false;

    const int x = piece.x + dx / 2;
    const Word y = piece.y + dy / 2;
    const unsigned x_step = std::midpoint(piece.x_step, before.x_step);
    const unsigned y_step = std::midpoint(piece.y_step, before.y_step);
    const bool changed = x != piece.x || y != piece.y || x_step != piece.x_step || y_step != piece.y_step;
    piece.x = x;
    piece.y = y;
    piece.x_step = x_step;
    piece.y_step = y_step;
    return changed;
}

} // namespace

void FrameInterpolation::begin(const Video &video, SpriteList objects, unsigned width, bool mark_vi)
{
    native.moving.reset();
    objects_move = false;
    const bool visible = (video.reg[1] & 64) && !(video.reg[0] & 1);
    const bool extended = mark_vi && objects.active;
    const bool scaled = video.reg[36] & 128;
    const Word mode = video.reg[12] & 0x87;
    const bool continuous = previous_width == width && previous_mode == mode && previous_extended == extended &&
        previous_mark_vi == mark_vi && previous_scaled == scaled;
    if (visible) {
        if (extended)
            match_objects(objects, continuous);
        else
            match_native(video, continuous);
    }
    previous_width = visible ? width : 0;
    previous_mode = mode;
    previous_extended = extended;
    previous_mark_vi = mark_vi;
    previous_scaled = scaled;
}

void FrameInterpolation::match_native(const Video &video, bool continuous)
{
    const unsigned table = (video.reg[5] & 127) * 256;
    const bool comparable = continuous && native.table == table;
    const bool scaled = video.reg[36] & 128;
    const unsigned transforms = (video.reg[36] & 31) * 2048;
    std::bitset<128> links;
    unsigned entry = 0;
    do {
        links.set(entry);
        const unsigned index = table | (entry * 4);
        const Word y = video.vram[index], shape = video.vram[index + 1];
        const Word descriptor = video.vram[index + 2], position = video.vram[index + 3];
        const unsigned transform = transforms + (position >> 9) * 8;
        const unsigned x_step = scaled ? std::min(4096u, video.vram[transform] & 32767u) / 64 : 64;
        const unsigned y_step = scaled ? (video.vram[transform + 3] & 32767) / 64 : 64;
        const SpritePiece current{int(position & 511) - 128, y, shape, descriptor, x_step, y_step};
        if (comparable && previous_links[entry] && current.x != -128 && previous_native[entry].x != -128) {
            auto midpoint = current;
            if (interpolate(midpoint, previous_native[entry])) {
                native.entries[entry] = {y, shape, descriptor, position, x_step, y_step, midpoint};
                native.moving.set(entry);
            }
        }
        previous_native[entry] = current;
        entry = shape & 127;
    } while (!links[entry]);
    previous_links = links;
    native.table = table;
}

void FrameInterpolation::match_objects(SpriteList objects, bool continuous)
{
    if (continuous && generation == objects.generation)
        return;
    if (continuous) {
        midpoint_objects.assign(objects.pieces.begin(), objects.pieces.end());
        for (auto &piece : midpoint_objects) {
            const auto match = std::lower_bound(previous_objects.begin(), previous_objects.end(), piece.identity,
                [](const SpritePiece &other, std::uint64_t id) { return other.identity < id; });
            if (match != previous_objects.end() && match->identity == piece.identity)
                objects_move |= interpolate(piece, *match);
        }
    }
    previous_objects.assign(objects.pieces.begin(), objects.pieces.end());
    std::sort(previous_objects.begin(), previous_objects.end(),
              [](const SpritePiece &a, const SpritePiece &b) { return a.identity < b.identity; });
    generation = objects.generation;
}

SpriteList FrameInterpolation::between_objects(SpriteList objects) const
{
    if (objects.active && objects_move && objects.generation == generation)
        return {true, midpoint_objects, generation};
    return {};
}

} // namespace markv
