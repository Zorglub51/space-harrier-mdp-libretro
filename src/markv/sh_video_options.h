// license:GPL-2.0-or-later
#pragma once
#include <atomic>
#include <cstdint>
#include <vector>
namespace sh_mdp_video {
inline std::atomic<bool> markvi{false};
inline std::atomic<bool> request_120{false};
// Independent host viewport preference; eligibility comes only from the
// authenticated SH1/SH2 cartridge profile. Apply at native-frame boundaries.
inline std::atomic<bool> request_wide{false};
inline std::atomic<bool> wide_eligible{false};
inline std::atomic<bool> widescreen{false};
inline constexpr unsigned native_width = 320, wide_width = 426;
// Source width differs from final output width when the alternate renderer
// scales to a user-selected resolution.
inline std::atomic<unsigned> source_width{0};
inline float aspect_for_source(unsigned width, float fallback)
{
    if (!wide_eligible.load(std::memory_order_relaxed)) return fallback;
    if (width == wide_width) return 16.0f / 9.0f;
    if (width == native_width) return 4.0f / 3.0f;
    return fallback;
}
// Changed only at a libretro frame boundary; the emulation/render threads are
// joined by retro_main_loop before their output is consumed.
inline std::atomic<bool> hz120{false};
inline bool second_half = false;
inline bool pending_draw = false;
inline unsigned pending_width = 0, pending_height = 0, pending_samples = 0;
inline unsigned pending_source_width = 0;
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
    pending_samples = pending_source_width = 0;
    source_width = 0;
    screen = nullptr; half_texture = nullptr;
}
}
