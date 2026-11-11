#include "machine.hpp"
#include "interpolation.hpp"

namespace markv {

void Machine::advance(unsigned cycles)
{
    bus.advance(cycles);
    if (bus.z80_in_reset()) {
        if (!z80_held_in_reset)
            sound_cpu.reset();
        z80_held_in_reset = true;
        z80_credit = 0;
        return;
    }
    z80_held_in_reset = false;
    if (!bus.z80_has_bus())
        return;
    z80_credit += int(cycles) * 7;
    while (z80_credit > 0)
        z80_credit -= int(sound_cpu.step(bus.z80_irq())) * 15;
}

void Machine::frame(FrameInterpolation *interpolation)
{
    constexpr unsigned blank_lines = lines_per_frame - screen_height;

    width = bus.widescreen() ? wide_width : screen_width;
    bus.begin_audio();
    for (slice = 0; slice < lines_per_frame; ++slice) {
        bus.begin_line(slice);
        if (slice >= blank_lines) {
            const unsigned y = slice - blank_lines;
            const bool interlace = (bus.video.reg[12] & 6) == 6;
            const auto objects = bus.observe_sprites() ? bus.scene() : SpriteList{};
            const std::span<Pixel> line(pixels.data() + y * width, width);
            IntermediateScanline intermediate;
            if (interpolation) {
                if (y == 0)
                    interpolation->begin(bus.video, objects, width, bus.mark_vi());
                intermediate = {interpolation->line(y, width), interpolation->between_objects(objects),
                                interpolation->between_native()};
            }
            renderer.render(bus.video, y, interlace, line, bus.mark_vi(), objects, intermediate);
        }
        master_credit += ticks_per_line;
        while (master_credit > 0) {
            const unsigned level = bus.interrupt_level();
            const unsigned interrupt_cycles = cpu.interrupt(level);
            if (interrupt_cycles) {
                bus.acknowledge(level);
                advance(interrupt_cycles);
                master_credit -= int(interrupt_cycles) * ticks_per_cpu_cycle;
            } else if (cpu.stopped) {
                advance(unsigned(master_credit / ticks_per_cpu_cycle));
                master_credit %= ticks_per_cpu_cycle;
                break;
            } else {
                const unsigned cycles = cpu.step();
                advance(cycles);
                master_credit -= int(cycles) * ticks_per_cpu_cycle;
                ++executed;
            }
        }
    }
    ++frames;
}

} // namespace markv
