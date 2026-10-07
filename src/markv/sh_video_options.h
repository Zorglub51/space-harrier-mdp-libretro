// license:GPL-2.0-or-later
#pragma once
#include <atomic>
#include <cstdint>
#include <vector>
namespace sh_mdp_video {
inline std::atomic<bool> markvi{false};
inline std::atomic<bool> request_120{false};
// Changed only at a libretro frame boundary; the emulation/render threads are
// joined by retro_main_loop before their output is consumed.
inline std::atomic<bool> hz120{false};
inline bool second_half = false;
inline bool pending_draw = false;
inline unsigned pending_width = 0, pending_height = 0, pending_samples = 0;
// Match the existing libretro framebuffer capacity. Saving the pending half
// frame makes rewind/save-load exact even between two 120 Hz presentations.
inline std::uint32_t pending_pixels[4096 * 3072]{};
inline std::int16_t pending_audio[32768]{};
// Transient render bridge. It follows the existing MAME primitive-list lock.
inline const void *screen = nullptr;
inline const std::uint32_t *half_texture = nullptr;
inline unsigned texture_width = 0, texture_height = 0, texture_stride = 0;
inline std::vector<std::uint32_t> half_output;
inline bool half_valid = false;
inline void clear_pending() {
    second_half = pending_draw = half_valid = false;
    pending_samples = 0;
    screen = nullptr; half_texture = nullptr;
}
}
