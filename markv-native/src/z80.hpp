#pragma once

#include "bus.hpp"

namespace markv {

struct Z80Fault {
    Word pc;
    Byte opcode;
};

class Z80 {
public:
    explicit Z80(Bus &bus) : bus(bus) {}
    void reset();
    unsigned step(bool interrupt);

    Word pc = 0;

private:
    static constexpr Byte sign = 0x80, zero = 0x40, half = 0x10;
    static constexpr Byte parity = 4, subtract = 2, carry = 1;
    static constexpr Byte high_flags = sign | zero | 0x28;

    Byte next();
    Byte operation();
    Word immediate();
    Word read_word(Word where);
    void write_word(Word where, Word value);
    void push(Word value);
    Word pop();
    Word pair(unsigned code, const Word *index = nullptr) const;
    void pair(unsigned code, Word value, Word *index = nullptr);
    Byte reg(unsigned code, const Word *index, Word memory);
    void reg(unsigned code, Word *index, Word memory, Byte value);
    bool condition(unsigned code) const;
    void alu(unsigned code, Byte right);
    static Byte flags(Byte value);
    unsigned decode(Byte opcode, Word *index);
    unsigned bits(Byte opcode, Word *index, Word memory);
    unsigned extended(Byte opcode);
    [[noreturn]] void unsupported(Byte opcode) const;

    Bus &bus;
    std::array<Byte, 8> r{}, alternate{};
    Word sp = 0xffff, ix = 0, iy = 0, start = 0;
    Byte interrupt_register = 0, refresh = 0;
    unsigned mode = 0, enable_delay = 0;
    bool iff = false, iff_shadow = false, halted = false;
};

} // namespace markv
