#pragma once

#include "m68k.hpp"
#include "z80.hpp"

namespace markv {

using Frame = std::array<Pixel, screen_width * screen_height>;
class FrameInterpolation;

class Machine {
public:
    explicit Machine(std::span<const Byte> cartridge) : bus(cartridge), cpu(bus), sound_cpu(bus) { cpu.reset(); }
    Machine(const Machine &) = delete;
    Machine &operator=(const Machine &) = delete;

    void frame(FrameInterpolation *interpolation = nullptr);
    std::span<const Pixel> video() const { return {pixels.data(), width * screen_height}; }
    unsigned video_width() const { return width; }
    std::span<const std::int16_t> audio() const { return bus.audio(); }
    unsigned line() const { return slice; }

    Bus bus;
    M68000 cpu;
    Z80 sound_cpu;
    std::uint64_t executed = 0;
    std::uint64_t frames = 0;

private:
    void advance(unsigned cycles);
    Renderer renderer;
    std::array<Pixel, wide_width * screen_height> pixels{};
    unsigned width = screen_width;
    int master_credit = 0, z80_credit = 0;
    bool z80_held_in_reset = true;
    unsigned slice = 0;
};

} // namespace markv
