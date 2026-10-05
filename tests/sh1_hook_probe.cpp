// license:GPL-2.0-or-later
#include "../src/markv/sh1_hooks.h"

#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>

struct FixtureBus
{
    std::map<std::uint32_t, std::uint16_t> words;
    std::vector<std::uint32_t> reads;

    std::uint16_t read_word(std::uint32_t address)
    {
        reads.push_back(address);
        return words.at(address);
    }
};

int main()
{
    markv::CpuState cpu;
    for (unsigned i = 0; i != 8; ++i)
    {
        cpu.d[i] = 0xabc00000u + i;
        cpu.a[i] = 0xdef00000u + i;
    }
    std::uint32_t flags, extend, ticks, count;
    if (!(std::cin >> cpu.d[1] >> cpu.d[4] >> cpu.d[6] >> cpu.a[0]
          >> cpu.a[2] >> cpu.a[4] >> flags >> extend >> ticks >> count)
        || flags > 255 || extend > 255 || count > 256)
        return 2;
    cpu.nzvc = std::uint8_t(flags);
    cpu.extend = std::uint8_t(extend);
    FixtureBus bus;
    for (std::uint32_t i = 0; i != count; ++i)
    {
        std::uint32_t address, value;
        if (!(std::cin >> address >> value) || value > 65535)
            return 2;
        bus.words[address] = std::uint16_t(value);
    }
    const auto before = cpu;
    try
    {
        const auto result = markv::sh1_collision_depth(cpu, bus, ticks);
        bool unchanged = cpu.extend == before.extend;
        for (unsigned i = 0; i != 8; ++i)
        {
            if (i != 1 && i != 4) unchanged &= cpu.d[i] == before.d[i];
            if (i != 0) unchanged &= cpu.a[i] == before.a[i];
        }
        std::cout << "{\"d1\":" << cpu.d[1] << ",\"d4\":" << cpu.d[4]
                  << ",\"d6\":" << cpu.d[6] << ",\"a0\":" << cpu.a[0]
                  << ",\"flags\":" << unsigned(cpu.nzvc)
                  << ",\"x\":" << unsigned(cpu.extend)
                  << ",\"next_pc\":" << result.next_pc
                  << ",\"ticks\":" << result.dispatch_counter
                  << ",\"unrelated_registers_preserved\":" << (unchanged ? "true" : "false")
                  << ",\"reads\":[";
        for (std::size_t i = 0; i != bus.reads.size(); ++i)
            std::cout << (i ? "," : "") << bus.reads[i];
        std::cout << "]}\n";
    }
    catch (const std::out_of_range &)
    {
        std::cerr << "Hook accessed a word absent from the reference fixture\n";
        return 3;
    }
}
