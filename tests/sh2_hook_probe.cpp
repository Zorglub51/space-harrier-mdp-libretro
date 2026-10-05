// license:GPL-2.0-or-later
#include "../src/markv/sh2_hooks.h"

#include <iostream>

int main()
{
    markv::CpuState cpu;
    for (unsigned i = 0; i != 8; ++i)
    {
        cpu.d[i] = 0xabc00000u + i;
        cpu.a[i] = 0xdef00000u + i;
    }
    std::uint32_t limit, flags, extend, ticks;
    if (!(std::cin >> cpu.d[0] >> cpu.d[1] >> cpu.d[4] >> cpu.a[0]
          >> limit >> flags >> extend >> ticks) || flags > 255 || extend > 255)
        return 2;
    cpu.nzvc = std::uint8_t(flags);
    cpu.extend = std::uint8_t(extend);
    const auto before = cpu;
    const auto result = markv::sh2_line_phase_tail(cpu, limit, ticks);
    bool unchanged = true;
    for (unsigned i = 0; i != 8; ++i)
    {
        if (i != 0 && i != 1) unchanged &= cpu.d[i] == before.d[i];
        if (i != 0 && i != 2 && i != 3) unchanged &= cpu.a[i] == before.a[i];
    }
    std::cout << "{\"d0\":" << cpu.d[0] << ",\"d1\":" << cpu.d[1]
              << ",\"d4\":" << cpu.d[4] << ",\"a0\":" << cpu.a[0]
              << ",\"a2\":" << cpu.a[2] << ",\"a3\":" << cpu.a[3]
              << ",\"flags\":" << unsigned(cpu.nzvc)
              << ",\"x\":" << unsigned(cpu.extend)
              << ",\"next_pc\":" << result.next_pc
              << ",\"ticks\":" << result.dispatch_counter
              << ",\"unrelated_registers_preserved\":" << (unchanged ? "true" : "false")
              << "}\n";
}
