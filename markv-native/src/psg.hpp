#pragma once

#include <array>
#include <cstdint>

namespace markv {

class Psg {
public:
    void write(std::uint8_t data);
    int sample(unsigned master_ticks);

private:
    struct Tone {
        unsigned period = 0, remaining = 1;
        bool high = true;
    };

    int tick();
    std::array<Tone, 3> tones{};
    std::array<unsigned, 4> volume{15, 15, 15, 15};
    unsigned latch = 0, noise_mode = 0, noise_remaining = 1, clock_remainder = 0;
    unsigned shift_register = 0x8000;
    bool noise_high = false;
};

} // namespace markv
