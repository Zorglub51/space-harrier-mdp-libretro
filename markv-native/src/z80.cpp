#include "z80.hpp"

#include <bit>
#include <utility>

namespace markv {

void Z80::reset()
{
    pc = 0;
    interrupt_register = refresh = 0;
    mode = enable_delay = 0;
    iff = iff_shadow = halted = false;
}

Byte Z80::next() { return bus.z80_read(pc++); }

Byte Z80::operation()
{
    refresh = (refresh & 128) | ((refresh + 1) & 127);
    return next();
}

Word Z80::immediate()
{
    const Byte low = next();
    return low | (Word(next()) << 8);
}

Word Z80::read_word(Word where)
{
    const Byte low = bus.z80_read(where);
    return low | (Word(bus.z80_read(Word(where + 1))) << 8);
}

void Z80::write_word(Word where, Word value)
{
    bus.z80_write(where, Byte(value));
    bus.z80_write(Word(where + 1), Byte(value >> 8));
}

void Z80::push(Word value)
{
    bus.z80_write(--sp, Byte(value >> 8));
    bus.z80_write(--sp, Byte(value));
}

Word Z80::pop()
{
    const Word value = read_word(sp);
    sp += 2;
    return value;
}

Word Z80::pair(unsigned code, const Word *index) const
{
    if (code == 3)
        return sp;
    if (code == 2 && index)
        return *index;
    return (Word(r[code * 2]) << 8) | r[code * 2 + 1];
}

void Z80::pair(unsigned code, Word value, Word *index)
{
    if (code == 3)
        sp = value;
    else if (code == 2 && index)
        *index = value;
    else {
        r[code * 2] = Byte(value >> 8);
        r[code * 2 + 1] = Byte(value);
    }
}

Byte Z80::reg(unsigned code, const Word *index, Word memory)
{
    if (code == 6)
        return bus.z80_read(memory);
    if (index && (code == 4 || code == 5))
        return code == 4 ? Byte(*index >> 8) : Byte(*index);
    return r[code];
}

void Z80::reg(unsigned code, Word *index, Word memory, Byte value)
{
    if (code == 6)
        bus.z80_write(memory, value);
    else if (index && (code == 4 || code == 5)) {
        *index = code == 4 ? Word((*index & 255) | (value << 8))
                           : Word((*index & 0xff00) | value);
    } else
        r[code] = value;
}

Byte Z80::flags(Byte value)
{
    return (value & (sign | 0x28)) | (value == 0 ? zero : 0) |
           (std::popcount(value) % 2 == 0 ? parity : 0);
}

bool Z80::condition(unsigned code) const
{
    constexpr Byte tested[] = {zero, carry, parity, sign};
    return ((r[6] & tested[code / 2]) != 0) == ((code & 1) != 0);
}

void Z80::alu(unsigned code, Byte right)
{
    const Byte left = r[7];
    if (code >= 4 && code <= 6) {
        const Byte value = code == 4 ? left & right : code == 5 ? left ^ right : left | right;
        r[7] = value;
        r[6] = flags(value) | (code == 4 ? half : 0);
        return;
    }
    const bool sub = code >= 2;
    const unsigned extra = (code == 1 || code == 3) && (r[6] & carry);
    const unsigned full = sub ? left - right - extra : left + right + extra;
    const Byte value = Byte(full);
    const bool v = sub ? (left ^ right) & (left ^ value) & sign :
                         ~(left ^ right) & (left ^ value) & sign;
    const Byte undocumented = code == 7 ? right & 0x28 : value & 0x28;
    r[6] = (value & sign) | undocumented | (value == 0 ? zero : 0) |
           (((left ^ right ^ value) & half) ? half : 0) | (v ? parity : 0) |
           (sub ? subtract : 0) | ((full & 256) ? carry : 0);
    if (code != 7)
        r[7] = value;
}

void Z80::unsupported(Byte opcode) const
{
    throw Z80Fault{start, opcode};
}

unsigned Z80::step(bool interrupt)
{
    if (interrupt && iff && !enable_delay) {
        iff = iff_shadow = false;
        halted = false;
        push(pc);
        pc = mode == 2 ? read_word((Word(interrupt_register) << 8) | 255) : 0x38;
        return mode == 2 ? 19 : 13;
    }
    if (enable_delay)
        --enable_delay;
    if (halted)
        return 4;

    start = pc;
    Word *index = nullptr;
    unsigned prefixes = 0;
    Byte opcode = operation();
    while (opcode == 0xdd || opcode == 0xfd) {
        index = opcode == 0xdd ? &ix : &iy;
        prefixes += 4;
        if (prefixes > 64)
            unsupported(opcode);
        opcode = operation();
    }
    if (opcode == 0xcb) {
        const Word location = index ? Word(*index + std::bit_cast<std::int8_t>(next())) : pair(2);
        return prefixes + bits(index ? next() : operation(), index, location);
    }
    if (opcode == 0xed)
        return prefixes + extended(operation());
    return prefixes + decode(opcode, index);
}

unsigned Z80::decode(Byte opcode, Word *index)
{
    const unsigned group = opcode >> 6;
    const unsigned y = (opcode >> 3) & 7, z = opcode & 7;
    const unsigned p = y >> 1;
    const bool q = y & 1;

    if (group == 1 && y == 6 && z == 6) {
        halted = true;
        return 4;
    }
    const bool indexed_memory = index && (
        (group == 1 && (y == 6 || z == 6)) || (group == 2 && z == 6) ||
        (group == 0 && y == 6 && z >= 4 && z <= 6));
    const Word memory = indexed_memory ? Word(*index + std::bit_cast<std::int8_t>(next())) : pair(2);
    const unsigned displacement_cycles = indexed_memory ? 8 : 0;

    if (group == 1) {
        Word *register_index = indexed_memory ? nullptr : index;
        const Byte value = reg(z, register_index, memory);
        reg(y, register_index, memory, value);
        return (y == 6 || z == 6 ? 7 : 4) + displacement_cycles;
    }
    if (group == 2) {
        alu(y, reg(z, index, memory));
        return (z == 6 ? 7 : 4) + displacement_cycles;
    }

    if (group == 0) {
        switch (z) {
        case 0: {
            if (y == 0)
                return 4;
            if (y == 1) {
                std::swap(r[6], alternate[6]);
                std::swap(r[7], alternate[7]);
                return 4;
            }
            const auto offset = std::bit_cast<std::int8_t>(next());
            bool take = true;
            if (y == 2)
                take = --r[0] != 0;
            else if (y >= 4)
                take = condition(y - 4);
            if (take)
                pc += offset;
            return (take ? 12 : 7) + (y == 2 ? 1 : 0);
        }
        case 1:
            if (!q) {
                pair(p, immediate(), index);
                return 10;
            } else {
                const unsigned left = pair(2, index), right = pair(p, index);
                const unsigned value = left + right;
                pair(2, Word(value), index);
                r[6] = (r[6] & (sign | zero | parity)) | ((value >> 8) & 0x28) |
                       (((left ^ right ^ value) & 0x1000) ? half : 0) | ((value >> 16) & 1);
                return 11;
            }
        case 2:
            if (p < 2) {
                if (q)
                    r[7] = bus.z80_read(pair(p));
                else
                    bus.z80_write(pair(p), r[7]);
                return 7;
            } else {
                const Word location = immediate();
                if (p == 2) {
                    if (q)
                        pair(2, read_word(location), index);
                    else
                        write_word(location, pair(2, index));
                    return 16;
                }
                if (q)
                    r[7] = bus.z80_read(location);
                else
                    bus.z80_write(location, r[7]);
                return 13;
            }
        case 3:
            pair(p, Word(pair(p, index) + (q ? -1 : 1)), index);
            return 6;
        case 4: case 5: {
            const Byte old = reg(y, index, memory);
            const bool dec = z == 5;
            const Byte value = Byte(old + (dec ? -1 : 1));
            reg(y, index, memory, value);
            r[6] = (r[6] & carry) | (flags(value) & ~parity) |
                   (((old ^ value) & half) ? half : 0) | (dec ? subtract : 0) |
                   (old == (dec ? 128 : 127) ? parity : 0);
            return (y == 6 ? 11 : 4) + displacement_cycles;
        }
        case 6:
            reg(y, index, memory, next());
            return y != 6 ? 7 : indexed_memory ? 15 : 10;
        case 7: {
            const Byte old = r[7];
            if (y < 4) {
                const bool left = !(y & 1);
                const Byte edge = left ? old >> 7 : old & 1;
                const Byte incoming = (y & 2) ? r[6] & carry : edge;
                r[7] = left ? Byte((old << 1) | incoming) : Byte((old >> 1) | (incoming << 7));
                r[6] = (r[6] & (sign | zero | parity)) | (r[7] & 0x28) | edge;
            } else if (y == 4) {
                const bool dec = r[6] & subtract;
                const bool decimal_carry = (r[6] & carry) || (!dec && old > 0x99);
                const unsigned correction = (decimal_carry ? 0x60 : 0) |
                    ((r[6] & half) || (!dec && (old & 15) > 9) ? 6 : 0);
                r[7] = Byte(dec ? old - correction : old + correction);
                r[6] = flags(r[7]) | (dec ? subtract : 0) | (decimal_carry ? carry : 0) |
                       ((old ^ r[7]) & half);
            } else if (y == 5) {
                r[7] = ~old;
                r[6] = (r[6] & ~0x28) | (r[7] & 0x28) | half | subtract;
            } else {
                const bool previous = r[6] & carry;
                r[6] = (r[6] & (sign | zero | parity)) | (old & 0x28) |
                    (y == 6 || !previous ? carry : 0) | (y == 7 && previous ? half : 0);
            }
            return 4;
        }
        }
    }

    switch (z) {
    case 0:
        if (condition(y)) {
            pc = pop();
            return 11;
        }
        return 5;
    case 1:
        if (!q) {
            const Word value = pop();
            if (p == 3) {
                r[6] = Byte(value);
                r[7] = Byte(value >> 8);
            } else
                pair(p, value, index);
            return 10;
        }
        if (p == 0) {
            pc = pop();
            return 10;
        }
        if (p == 1) {
            for (unsigned i = 0; i < 6; ++i)
                std::swap(r[i], alternate[i]);
            return 4;
        }
        if (p == 2) {
            pc = pair(2, index);
            return 4;
        }
        sp = pair(2, index);
        return 6;
    case 2: {
        const Word target = immediate();
        if (condition(y))
            pc = target;
        return 10;
    }
    case 3:
        switch (y) {
        case 0: pc = immediate(); return 10;
        case 2: next(); return 11;
        case 3: next(); r[7] = 255; return 11;
        case 4: {
            const Word memory_word = read_word(sp);
            write_word(sp, pair(2, index));
            pair(2, memory_word, index);
            return 19;
        }
        case 5: std::swap(r[2], r[4]); std::swap(r[3], r[5]); return 4;
        case 6: iff = iff_shadow = false; enable_delay = 0; return 4;
        case 7: iff = iff_shadow = true; enable_delay = 1; return 4;
        default: unsupported(opcode);
        }
    case 4: {
        const Word target = immediate();
        if (!condition(y))
            return 10;
        push(pc);
        pc = target;
        return 17;
    }
    case 5:
        if (!q) {
            push(p == 3 ? (Word(r[7]) << 8) | r[6] : pair(p, index));
            return 11;
        }
        if (p == 0) {
            const Word target = immediate();
            push(pc);
            pc = target;
            return 17;
        }
        unsupported(opcode);
    case 6:
        alu(y, next());
        return 7;
    case 7:
        push(pc);
        pc = Word(y * 8);
        return 11;
    }
    unsupported(opcode);
}

unsigned Z80::bits(Byte opcode, Word *index, Word memory)
{
    const unsigned type = opcode >> 6, bit = (opcode >> 3) & 7, code = opcode & 7;
    const unsigned target = index ? 6 : code;
    Byte value = reg(target, nullptr, memory);
    if (type == 1) {
        const bool set = value & (1u << bit);
        const Byte undocumented = index ? Byte(memory >> 8) : value;
        r[6] = (r[6] & carry) | half | (undocumented & 0x28) |
               (set ? (bit == 7 ? sign : 0) : zero | parity);
        return index ? 16 : target == 6 ? 12 : 8;
    }
    if (type == 2)
        value &= ~(1u << bit);
    else if (type == 3)
        value |= 1u << bit;
    else {
        const bool left = (bit & 1) == 0;
        const Byte edge = left ? value >> 7 : value & 1;
        Byte incoming = 0;
        if (bit < 2)
            incoming = edge;
        else if (bit < 4)
            incoming = r[6] & carry;
        else if (bit == 5)
            incoming = value >> 7;
        else if (bit == 6)
            incoming = 1;
        value = left ? Byte((value << 1) | incoming) : Byte((value >> 1) | (incoming << 7));
        r[6] = flags(value) | edge;
    }
    reg(target, nullptr, memory, value);
    if (index && code != 6)
        r[code] = value;
    return index ? 19 : target == 6 ? 15 : 8;
}

unsigned Z80::extended(Byte opcode)
{
    const unsigned y = (opcode >> 3) & 7;
    const unsigned z = opcode & 7;
    const unsigned p = y >> 1;
    if ((opcode & 0xc0) == 0x40) {
        switch (z) {
        case 0:
            if (y != 6)
                r[y] = 255;
            r[6] = (r[6] & carry) | flags(255);
            return 12;
        case 1: return 12;
        case 2: {
            const unsigned left = pair(2), right = pair(p), x = r[6] & carry;
            const bool sub = (y & 1) == 0;
            const unsigned full = sub ? left - right - x : left + right + x;
            const Word value = Word(full);
            const bool v = sub ? (left ^ right) & (left ^ value) & 0x8000 :
                                 ~(left ^ right) & (left ^ value) & 0x8000;
            pair(2, value);
            r[6] = ((value >> 8) & (sign | 0x28)) | (value ? 0 : zero) |
                   ((left ^ right ^ value) & 0x1000 ? half : 0) | (v ? parity : 0) |
                   (sub ? subtract : 0) | ((full >> 16) & 1);
            return 15;
        }
        case 3: {
            const Word location = immediate();
            if (y & 1)
                pair(p, read_word(location));
            else
                write_word(location, pair(p));
            return 20;
        }
        case 4: {
            const Byte value = r[7];
            r[7] = 0;
            alu(2, value);
            return 8;
        }
        case 5:
            pc = pop();
            iff = iff_shadow;
            return 14;
        case 6: {
            constexpr unsigned modes[] = {0, 0, 1, 2, 0, 0, 1, 2};
            mode = modes[y];
            return 8;
        }
        case 7:
            if (y == 0)
                interrupt_register = r[7];
            else if (y == 1)
                refresh = r[7];
            else if (y < 4) {
                r[7] = y == 2 ? interrupt_register : refresh;
                r[6] = (r[6] & carry) | (flags(r[7]) & ~parity) | (iff_shadow ? parity : 0);
            } else if (y < 6) {
                const Word location = pair(2);
                const Byte memory = bus.z80_read(location), accumulator = r[7];
                if (y == 4) {
                    bus.z80_write(location, Byte((accumulator << 4) | (memory >> 4)));
                    r[7] = (accumulator & 0xf0) | (memory & 15);
                } else {
                    bus.z80_write(location, Byte((memory << 4) | (accumulator & 15)));
                    r[7] = (accumulator & 0xf0) | (memory >> 4);
                }
                r[6] = (r[6] & carry) | flags(r[7]);
                return 18;
            } else
                return 8;
            return 9;
        }
    }
    if ((opcode & 0xe6) == 0xa0) {
        const int delta = (opcode & 8) ? -1 : 1;
        const bool compare = opcode & 1;
        const Word source = pair(2);
        const Byte value = bus.z80_read(source);
        pair(2, Word(source + delta));
        const Word count = Word(pair(0) - 1);
        pair(0, count);
        if (compare) {
            const Byte saved = r[6] & carry;
            alu(7, value);
            const unsigned adjusted = r[7] - value - ((r[6] & half) ? 1 : 0);
            r[6] = (r[6] & (sign | zero | half | subtract)) | saved |
                (count ? parity : 0) | (adjusted & 8) | ((adjusted & 2) << 4);
        } else {
            const Word target = pair(1);
            bus.z80_write(target, value);
            pair(1, Word(target + delta));
            const unsigned sum = r[7] + value;
            r[6] = (r[6] & (sign | zero | carry)) | (count ? parity : 0) |
                   (sum & 8) | ((sum & 2) << 4);
        }
        if ((opcode & 16) && count && (!compare || !(r[6] & zero))) {
            pc -= 2;
            return 21;
        }
        return 16;
    }
    unsupported(opcode);
}

} // namespace markv
