#include "psg.hpp"

#include <algorithm>

namespace markv {

void Psg::write(std::uint8_t data)
{
    const bool new_latch = data & 128;
    if (new_latch)
        latch = (data >> 4) & 7;
    const unsigned channel = latch >> 1;
    if (latch & 1) {
        volume[channel] = data & 15;
    } else if (channel == 3) {
        noise_mode = data & 7;
        shift_register = 0x8000;
    } else {
        auto &tone = tones[channel];
        tone.period = new_latch ? ((tone.period & 0x3f0) | (data & 15)) :
            ((tone.period & 15) | ((data & 63) << 4));
    }
}

int Psg::tick()
{
    constexpr int levels[] = {1024, 813, 646, 513, 408, 324, 257, 204, 162, 129, 102, 81, 65, 51, 41, 0};
    int output = 0;
    bool tone_two_edge = false;
    for (unsigned i = 0; i < tones.size(); ++i) {
        auto &tone = tones[i];
        if (!--tone.remaining) {
            tone.remaining = std::max(1u, tone.period);
            tone.high = !tone.high;
            tone_two_edge = i == 2 && tone.high;
        }
        output += (tone.high || tone.period < 2) ? levels[volume[i]] : -levels[volume[i]];
    }

    const unsigned rate = noise_mode & 3;
    bool clock_noise = tone_two_edge;
    if (rate != 3) {
        clock_noise = !--noise_remaining;
        if (clock_noise) {
            noise_remaining = 16u << rate;
            noise_high = !noise_high;
            clock_noise = noise_high;
        }
    }
    if (clock_noise) {
        const unsigned feedback = (shift_register ^ ((noise_mode & 4) ? shift_register >> 3 : 0)) & 1;
        shift_register = (shift_register >> 1) | (feedback << 15);
    }
    return output + ((shift_register & 1) ? levels[volume[3]] : -levels[volume[3]]);
}

int Psg::sample(unsigned master_ticks)
{
    constexpr unsigned master_ticks_per_psg_tick = 15 * 16;
    clock_remainder += master_ticks;
    const unsigned ticks = clock_remainder / master_ticks_per_psg_tick;
    clock_remainder %= master_ticks_per_psg_tick;
    int sum = 0;
    for (unsigned i = 0; i < ticks; ++i)
        sum += tick();
    return ticks ? sum / int(ticks) : 0;
}

} // namespace markv
