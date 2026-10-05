// license:GPL-2.0-or-later
#pragma once

#include "sh1_hooks.h"

namespace markv {

constexpr std::uint8_t long_nz(std::uint32_t value)
{
    return value == 0 ? 4 : (value & 0x80000000u) ? 8 : 0;
}

// Independently testable reference for SH2 guest 0x18bcf4..0x18bd08,
// original ARM Thumb file offset 0x0bf174. Not an installed MAME CPU hook.
// limit is the logical big-endian long read from guest address 0xff116a.
inline HookExit sh2_line_phase_tail(CpuState &cpu, std::uint32_t limit,
                                   std::uint32_t dispatch_counter)
{
    cpu.d[1] = cpu.d[4]; // MOVE.L D4,D1: the reconstructed opcode is 2204.
    cpu.a[0] += 0x10u;
    const auto previous_d0 = cpu.d[0];
    cpu.d[0] += 1u;
    // M2's separate X byte retains the whole flags snapshot of the last
    // X-writing operation; only its carry bit is the architectural X flag.
    cpu.extend = std::uint8_t(long_nz(cpu.d[0])
        | (previous_d0 == 0x7fffffffu ? 2 : 0)
        | (previous_d0 == 0xffffffffu ? 1 : 0));
    cpu.a[3] = limit;
    cpu.a[2] = limit - 0x40u;
    const auto result = cpu.d[0] - cpu.a[2];
    const bool overflow = ((cpu.d[0] ^ cpu.a[2]) & (cpu.d[0] ^ result)
                           & 0x80000000u) != 0;
    cpu.nzvc = std::uint8_t(long_nz(result) | (overflow ? 2 : 0)
                          | (cpu.d[0] < cpu.a[2] ? 1 : 0));
    const bool less = ((result & 0x80000000u) != 0) != overflow;
    return {less ? 0x0018bcd0u : 0x0018bd0au,
            dispatch_counter + (less ? 64u : 62u)};
}

} // namespace markv
