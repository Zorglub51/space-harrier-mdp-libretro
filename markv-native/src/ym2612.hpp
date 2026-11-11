#pragma once

#include <array>
#include <cstdint>

namespace markv {

class Ym2612 {
public:
    void write(unsigned bank, unsigned reg, std::uint8_t value);
    std::array<int, 2> sample(unsigned fm_level = 100, unsigned pcm_level = 100);

private:
    enum Stage { attack, decay, sustain, release, off };
    static constexpr unsigned attenuation_bits = 16;
    static constexpr unsigned max_attenuation = 1023 << attenuation_bits;

    struct Operator {
        std::uint32_t phase = 0, step = 0;
        unsigned attenuation = max_attenuation;
        std::array<unsigned, 4> envelope_step{};
        unsigned multiple = 0, detune = 0, key_scale = 0;
        unsigned attack_rate = 0, decay_rate = 0, sustain_rate = 0, release_rate = 0;
        unsigned total_level = 0, sustain_level = 0;
        Stage stage = off;
        bool held = false, instant_attack = false;

        void configure(unsigned fnum, unsigned block);
        void key(bool pressed);
        int sample(int modulation);
    };

    struct Channel {
        std::array<Operator, 4> slots{};
        int feedback_sample = 0, previous_feedback = 0;
        unsigned frequency = 0, block = 0, algorithm = 0, feedback = 0;
        unsigned pan = 0;

        int sample();
    };

    std::array<Channel, 6> channels{};
    unsigned frequency_high = 0;
    int dac = 0;
    bool dac_enabled = false;
};

} // namespace markv
