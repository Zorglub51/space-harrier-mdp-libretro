// license:GPL-2.0-or-later
#pragma once

#include "sh1_hooks.h"

namespace markv {

// Reference for guest 0x190a80..0x190a88, original ARM file offset 0x0be9ac.
// The installed core executes the reconstructed 68000 instructions instead.
// Bus callbacks describe the native handler boundary: the read address is
// masked to 24 bits here; the write callback receives the full A1 register.
template <typename Bus>
HookExit sh2_tilemap_copy_word(CpuState &cpu, Bus &bus, std::uint32_t ticks)
{
    // MOVE.W (A0)+,D6 is 3C18. The former 30C1 wrote D1 into the source.
    const auto source = std::uint16_t(bus.read_word(cpu.a[0] & 0x00ffffffu));
    cpu.a[0] += 2u;
    const auto base = std::uint16_t(cpu.d[1]);
    const auto sum = std::uint32_t(source) + base;
    const auto value = std::uint16_t(sum);
    cpu.d[6] = (cpu.d[6] & 0xffff0000u) | value;
    // M2 stores the whole last ADD flags snapshot in its separate X byte.
    const bool add_overflow = ((source ^ value) & (base ^ value) & 0x8000u) != 0;
    cpu.extend = std::uint8_t((value == 0 ? 4 : (value & 0x8000u) ? 8 : 0)
        | (add_overflow ? 2 : 0) | (sum > 0xffffu ? 1 : 0));
    bus.write_word(cpu.a[1], value);
    cpu.a[1] += 2u;

    const auto result = cpu.d[0] - cpu.a[0];
    const bool compare_overflow = ((cpu.d[0] ^ cpu.a[0]) & (cpu.d[0] ^ result)
                                  & 0x80000000u) != 0;
    cpu.nzvc = std::uint8_t((result == 0 ? 4 : (result & 0x80000000u) ? 8 : 0)
        | (compare_overflow ? 2 : 0) | (cpu.d[0] < cpu.a[0] ? 1 : 0));
    const bool done = result == 0;
    return {done ? 0x00190a8au : 0x00190a80u, ticks + (done ? 34u : 36u)};
}

} // namespace markv
