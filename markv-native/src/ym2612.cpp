#include "ym2612.hpp"

#include <algorithm>

namespace markv {
namespace {

constexpr unsigned phase_shift = 22;

constexpr auto wave_table()
{
    std::array<int, 1024> wave{};
    for (unsigned i = 0; i < 256; ++i) {
        const double x = (i + 0.5) * 1.5707963267948966 / 256;
        double term = x;
        double sum = term;
        for (int order = 3; order <= 13; order += 2) {
            term *= -x * x / (order * (order - 1));
            sum += term;
        }
        const int amplitude = int(4095 * sum + 0.5);
        wave[i] = wave[511 - i] = amplitude;
        wave[512 + i] = wave[1023 - i] = -amplitude;
    }
    return wave;
}

constexpr auto gain_table()
{
    std::array<int, 1024> gains{};
    double gain = 32768;
    for (unsigned i = 0; i < 1023; ++i) {
        gains[i] = int(gain + 0.5);
        gain *= 0.9892646717677409; // 0.09375 dB of attenuation per step.
    }
    return gains;
}

constexpr auto wave = wave_table();
constexpr auto gains = gain_table();

} // namespace

void Ym2612::Operator::configure(unsigned fnum, unsigned block)
{
    // An octave divides into four key-code regions for detune and rate scaling.
    const unsigned fcode = fnum >> 7;
    const unsigned note = unsigned(fcode >= 7) + unsigned(fcode >= 8) + unsigned(fcode >= 9);
    const unsigned keycode = block * 4 + note;
    const unsigned scale = keycode >> (3 - key_scale);
    const std::array settings{attack_rate, decay_rate, sustain_rate, release_rate * 2 + 1};
    // Fractional steps approximate the progression of the hardware rate
    // generator. The fractional bits keep low rates advancing between samples.
    for (unsigned i = 0; i < settings.size(); ++i) {
        const unsigned rate = settings[i] ? std::min(63u, settings[i] * 2 + scale) : 0;
        envelope_step[i] = rate ? ((4 + (rate & 3)) << (rate >> 2)) * 4 / 3 : 0;
    }
    instant_attack = attack_rate && attack_rate * 2 + scale >= 62;

    const int adjustment = int((detune & 3) * (keycode + 4) / 8);
    const int delta = int((fnum << block) >> 1) + ((detune & 4) ? -adjustment : adjustment);
    step = unsigned(std::max(delta, 0)) * (multiple ? multiple * 4096 : 2048);
}

void Ym2612::Operator::key(bool pressed)
{
    if (pressed == held)
        return;
    held = pressed;
    if (pressed) {
        phase = 0;
        stage = attack;
        if (instant_attack)
            attenuation = 0;
    } else if (stage != off) {
        stage = release;
    }
}

int Ym2612::Operator::sample(int modulation)
{
    if (stage == off)
        return 0;
    const unsigned increment = envelope_step[stage];
    if (stage == attack) {
        if (increment) {
            const std::uint64_t distance = attenuation + (1u << attenuation_bits);
            const unsigned change = std::max(1u, unsigned((distance * increment) >> (attenuation_bits + 3)));
            attenuation -= std::min(attenuation, change);
        }
        if (!attenuation)
            stage = decay;
    } else {
        attenuation = std::min(max_attenuation, attenuation + increment);
        if (stage == decay && attenuation >= sustain_level)
            stage = sustain;
        if (attenuation == max_attenuation && stage != decay) {
            stage = off;
            return 0;
        }
    }
    const unsigned level = std::min(1023u, (attenuation >> attenuation_bits) + total_level);
    const unsigned index = ((phase >> phase_shift) + unsigned(modulation)) & 1023;
    phase += step;
    return (wave[index] * gains[level]) >> 15;
}

int Ym2612::Channel::sample()
{
    const int a = slots[0].sample(feedback ? ((feedback_sample + previous_feedback) >> (10 - feedback)) : 0);
    previous_feedback = feedback_sample;
    feedback_sample = a;
    // The chip feeds bits 1–10 of the 14-bit operator result into the phase
    // adder. Our half-scale operator result is already in those phase units.
    const auto b = [this](int m) { return slots[1].sample(m); };
    const auto c = [this](int m) { return slots[2].sample(m); };
    const auto d = [this](int m) { return slots[3].sample(m); };
    switch (algorithm) {
    case 0: return d(c(b(a)));
    case 1: return d(c(a + b(0)));
    case 2: return d(a + c(b(0)));
    case 3: return d(b(a) + c(0));
    case 4: return b(a) + d(c(0));
    case 5: return b(a) + c(a) + d(a);
    case 6: return b(a) + c(0) + d(0);
    default: return a + b(0) + c(0) + d(0);
    }
}

void Ym2612::write(unsigned bank, unsigned reg, std::uint8_t value)
{
    if (reg < 0x30) {
        if (bank)
            return;
        switch (reg) {
        case 0x28: {
            const unsigned channel = value & 3;
            if (channel == 3)
                return;
            auto &slots = channels[channel + ((value & 4) ? 3 : 0)].slots;
            for (unsigned i = 0; i < slots.size(); ++i)
                slots[i].key(value & (16u << i));
            return;
        }
        case 0x2a: dac = (int(value) - 128) * 32; return;
        case 0x2b: dac_enabled = value & 128; return;
        default: return;
        }
    }

    const unsigned index = reg & 3;
    if (index == 3)
        return;
    auto &channel = channels[index + bank * 3];
    if (reg < 0x90) {
        constexpr std::array<unsigned, 4> slot_order{0, 2, 1, 3};
        auto &slot = channel.slots[slot_order[(reg >> 2) & 3]];
        switch (reg & 0xf0) {
        case 0x30: slot.multiple = value & 15; slot.detune = (value >> 4) & 7; break;
        case 0x40: slot.total_level = (value & 127) * 8; return;
        case 0x50: slot.key_scale = value >> 6; slot.attack_rate = value & 31; break;
        case 0x60: slot.decay_rate = value & 31; break;
        case 0x70: slot.sustain_rate = value & 31; break;
        case 0x80:
            slot.sustain_level = ((value >> 4) == 15 ? 31 : (value >> 4)) * (32 << attenuation_bits);
            slot.release_rate = value & 15;
            break;
        }
        slot.configure(channel.frequency, channel.block);
    } else {
        switch (reg & 0xfc) {
        case 0xa0:
            channel.frequency = ((frequency_high & 7) << 8) | value;
            channel.block = (frequency_high >> 3) & 7;
            for (auto &slot : channel.slots)
                slot.configure(channel.frequency, channel.block);
            break;
        case 0xa4: frequency_high = value; break;
        case 0xb0: channel.algorithm = value & 7; channel.feedback = (value >> 3) & 7; break;
        case 0xb4: channel.pan = value >> 6; break;
        }
    }
}

std::array<int, 2> Ym2612::sample(unsigned fm_level, unsigned pcm_level)
{
    std::array<int, 2> stereo{};
    for (unsigned i = 0; i < channels.size(); ++i) {
        auto &channel = channels[i];
        const int fm = channel.sample();
        if (i == 5 && dac_enabled)
            break;
        const int output = std::clamp(fm, -4096, 4095);
        if (channel.pan & 2)
            stereo[0] += output;
        if (channel.pan & 1)
            stereo[1] += output;
    }
    if (fm_level != 100) {
        for (int &side : stereo)
            side = side * int(fm_level) / 100;
    }
    if (dac_enabled) {
        const unsigned pan = channels.back().pan;
        const int output = pcm_level == 100 ? dac : dac * int(pcm_level) / 100;
        if (pan & 2)
            stereo[0] += output;
        if (pan & 1)
            stereo[1] += output;
    }
    return stereo;
}

} // namespace markv
