#pragma once

namespace markv {

inline constexpr unsigned master_hz = 53693175;
inline constexpr unsigned lines_per_frame = 262;
inline constexpr int ticks_per_line = 3420;
inline constexpr int ticks_per_cpu_cycle = 7;
inline constexpr int cycles_per_sample = 144;
inline constexpr unsigned ticks_per_sample = cycles_per_sample * ticks_per_cpu_cycle;
inline constexpr unsigned ticks_per_frame = lines_per_frame * ticks_per_line;
inline constexpr double frame_rate = double(master_hz) / ticks_per_frame;
inline constexpr double sample_rate = double(master_hz) / ticks_per_sample;

} // namespace markv
