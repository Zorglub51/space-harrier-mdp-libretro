#pragma once

#include "ym2612.hpp"

#include <array>
#include <cstdint>

namespace markv {

class FmPorts {
public:
    void advance(unsigned cycles) { clocks += cycles; }
    std::array<int, 2> sample(unsigned fm, unsigned pcm) { return synth.sample(fm, pcm); }

    std::uint8_t status()
    {
        update_timers();
        return flags | (clocks < busy_until ? 0x80 : 0);
    }

    void write(unsigned port, std::uint8_t value)
    {
        const unsigned bank = (port >> 1) & 1;
        if (!(port & 1)) {
            address[bank] = value;
            return;
        }

        update_timers();
        busy_until = clocks + 192;
        synth.write(bank, address[bank], value);
        if (bank)
            return;
        switch (address[0]) {
        case 0x24: timer_a = (timer_a & 3) | (value << 2); break;
        case 0x25: timer_a = (timer_a & 0x3fc) | (value & 3); break;
        case 0x26: timer_b = value; break;
        case 0x27:
            flags &= ~((value >> 4) & 3);
            for (unsigned timer = 0; timer < 2; ++timer)
                if ((value & (1u << timer)) && !(control & (1u << timer)))
                    deadline[timer] = clocks + period(timer);
            control = value;
            break;
        }
    }

private:
    unsigned period(unsigned timer) const
    {
        return timer == 0 ? 144 * (1024 - timer_a) : 2304 * (256 - timer_b);
    }

    void update_timers()
    {
        for (unsigned timer = 0; timer < 2; ++timer) {
            const unsigned bit = 1u << timer;
            if ((control & bit) && clocks >= deadline[timer]) {
                if (control & (bit << 2))
                    flags |= bit;
                const auto interval = period(timer);
                deadline[timer] += ((clocks - deadline[timer]) / interval + 1) * interval;
            }
        }
    }

    std::array<std::uint8_t, 2> address{};
    Ym2612 synth;
    std::array<std::uint64_t, 2> deadline{};
    std::uint64_t clocks = 0, busy_until = 0;
    unsigned timer_a = 0, timer_b = 0;
    std::uint8_t control = 0, flags = 0;
};

} // namespace markv
