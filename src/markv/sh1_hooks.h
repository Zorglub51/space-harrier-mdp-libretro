// license:GPL-2.0-or-later
#pragma once

#include <array>
#include <cstdint>

namespace markv {

// Portable representation, not an overlay of the original ARM allocation.
// M2 keeps NZVC and X in separate bytes at CPU-context offsets 0x1e and 0x1f.
struct CpuState
{
    std::array<std::uint32_t, 8> d{};
    std::array<std::uint32_t, 8> a{};
    std::uint8_t nzvc = 0;
    std::uint8_t extend = 0;
};

struct HookExit
{
    std::uint32_t next_pc;
    std::uint32_t dispatch_counter;
};

constexpr std::int32_t signed_word(std::uint16_t value)
{
    // Avoid implementation-defined conversion from an out-of-range uint16_t
    // to int16_t. The difference of two signed words fits in int32_t.
    return value < 0x8000u ? std::int32_t(value) : std::int32_t(value) - 0x10000;
}

// SH1 guest PC 0x19b93e, native Thumb entry 0x0d57c5 in the pinned m2engage.
// This block resumes at 0x19b94a, after four guest instructions. It is a first
// independently testable translation, not yet installed as a MAME CPU hook.
//
// Bus::read_word receives an even 24-bit guest address and returns its logical
// 16-bit value. The alignment here is specific to this M2 HLE path; it must not
// silently change the alignment checks of ordinary 68000 memory accesses.
template <typename Bus>
HookExit sh1_collision_depth(CpuState &cpu, Bus &bus, std::uint32_t dispatch_counter)
{
    // Preserve the actual ARM read order (A2 first), including page aliasing.
    const auto depth_a2 = std::uint16_t(bus.read_word((cpu.a[2] + 0xau) & 0x00fffffeu));
    const auto depth_a4 = std::uint16_t(bus.read_word((cpu.a[4] + 0xau) & 0x00fffffeu));

    cpu.d[1] = (cpu.d[1] & 0xffff0000u) | depth_a4;
    cpu.d[4] = (cpu.d[4] & 0xffff0000u) | depth_a2;
    cpu.a[0] = std::uint32_t(signed_word(depth_a4) - signed_word(depth_a2));
    // MOVE.W from A2 determines NZVC. MOVEA/SUBA do not update it. X survives.
    cpu.nzvc = depth_a2 == 0 ? 4 : (depth_a2 & 0x8000u) ? 8 : 0;

    // Reproduce R1 += 0x24 and R2 = 0x19b94a at the dispatcher boundary.
    return {0x0019b94au, dispatch_counter + 0x24u};
}

} // namespace markv
