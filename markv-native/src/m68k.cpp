#include "m68k.hpp"

#include <bit>
#include <limits>

namespace markv {

using U32 = std::uint32_t;

void M68000::reset()
{
    data.fill(0);
    address.fill(0);
    user_stack = supervisor_stack = 0;
    sr = 0x2700;
    address[7] = bus.read32(0);
    pc = bus.read32(4);
    stopped = false;
}

Word M68000::fetch()
{
    const Word value = Word(read_memory(pc, Size::word));
    pc += 2;
    return value;
}

U32 M68000::fetch_immediate(Size size)
{
    const Word first = fetch();
    if (size == Size::longword)
        return (U32(first) << 16) | fetch();
    return first & mask(size);
}

U32 M68000::read_memory(U32 location, Size size)
{
    if (size == Size::byte)
        return bus.read8(location);
    if (location & 1)
        throw CpuFault{CpuFault::Reason::address, instruction_pc, opcode, location};
    return size == Size::word ? bus.read16(location) : bus.read32(location);
}

void M68000::write_memory(U32 location, Size size, U32 value)
{
    if (size == Size::byte) {
        bus.write8(location, Byte(value));
        return;
    }
    if (location & 1)
        throw CpuFault{CpuFault::Reason::address, instruction_pc, opcode, location};
    if (size == Size::word)
        bus.write16(location, Word(value));
    else
        bus.write32(location, value);
}

U32 M68000::mask(Size size)
{
    if (size == Size::longword)
        return ~U32{0};
    return (U32{1} << (bytes(size) * 8)) - 1;
}

U32 M68000::signed_value(U32 value, Size size)
{
    const U32 width_mask = mask(size);
    const U32 sign = (width_mask >> 1) + 1;
    return ((value & width_mask) ^ sign) - sign;
}

M68000::Size M68000::size_field(unsigned value) const
{
    if (value == 3)
        invalid();
    return Size(1u << value);
}

U32 M68000::indexed(U32 base)
{
    const Word extension = fetch();
    const unsigned reg = (extension >> 12) & 7;
    U32 index = (extension & 0x8000) ? address[reg] : data[reg];
    if (!(extension & 0x0800))
        index = signed_value(index, Size::word);
    return base + index + signed_value(extension, Size::byte);
}

M68000::Operand M68000::operand(unsigned mode, unsigned reg, Size size)
{
    const unsigned cost = size == Size::longword ? 8 : 4;
    const unsigned delta = size == Size::byte && reg == 7 ? 2 : bytes(size);
    switch (mode) {
    case 0: return {Kind::data, reg, 0};
    case 1:
        if (size == Size::byte)
            invalid();
        return {Kind::address, reg, 0};
    case 2: return {Kind::memory, address[reg], cost};
    case 3: {
        const U32 old = address[reg];
        address[reg] += delta;
        return {Kind::memory, old, cost};
    }
    case 4:
        address[reg] -= delta;
        return {Kind::memory, address[reg], cost + 2};
    case 5: return {Kind::memory, address[reg] + signed_value(fetch(), Size::word), cost + 4};
    case 6: return {Kind::memory, indexed(address[reg]), cost + 6};
    case 7:
        switch (reg) {
        case 0: return {Kind::memory, signed_value(fetch(), Size::word), cost + 4};
        case 1: return {Kind::memory, fetch_immediate(Size::longword), cost + 8};
        case 2: {
            const U32 base = pc;
            return {Kind::memory, base + signed_value(fetch(), Size::word), cost + 4};
        }
        case 3: return {Kind::memory, indexed(pc), cost + 6};
        case 4: return {Kind::immediate, fetch_immediate(size), cost};
        default: break;
        }
        break;
    }
    invalid();
}

U32 M68000::read(Operand source, Size size)
{
    switch (source.kind) {
    case Kind::data: return data[source.value] & mask(size);
    case Kind::address: return address[source.value] & mask(size);
    case Kind::memory: return read_memory(source.value, size);
    case Kind::immediate: return source.value;
    }
    invalid();
}

void M68000::write(Operand destination, Size size, U32 value)
{
    const U32 width_mask = mask(size);
    switch (destination.kind) {
    case Kind::data:
        data[destination.value] = (data[destination.value] & ~width_mask) | (value & width_mask);
        return;
    case Kind::address:
        address[destination.value] = signed_value(value, size);
        return;
    case Kind::memory:
        write_memory(destination.value, size, value);
        return;
    case Kind::immediate:
        invalid();
    }
}

void M68000::push(U32 value, Size size)
{
    address[7] -= bytes(size);
    write_memory(address[7], size, value);
}

U32 M68000::pop(Size size)
{
    const U32 value = read_memory(address[7], size);
    address[7] += bytes(size);
    return value;
}

void M68000::status(Word value)
{
    if ((sr ^ value) & supervisor) {
        if (sr & supervisor) {
            supervisor_stack = address[7];
            address[7] = user_stack;
        } else {
            user_stack = address[7];
            address[7] = supervisor_stack;
        }
    }
    sr = value & 0xa71f;
}

void M68000::exception(unsigned vector)
{
    const Word previous = sr;
    status((sr | supervisor) & 0x7fff);
    push(pc, Size::longword);
    push(previous, Size::word);
    pc = bus.read32(vector * 4);
    stopped = false;
}

unsigned M68000::interrupt(unsigned level)
{
    if (!level || (level != 7 && level <= ((sr >> 8) & 7u)))
        return 0;
    exception(24 + level);
    status((sr & ~0x0700) | (level << 8));
    return 44;
}

void M68000::require_supervisor() const
{
    if (!(sr & supervisor))
        throw CpuFault{CpuFault::Reason::privilege, instruction_pc, opcode, 0};
}

bool M68000::condition(unsigned code) const
{
    const bool c = sr & carry, v = sr & overflow, z = sr & zero, n = sr & negative;
    switch (code) {
    case 0: return true;
    case 1: return false;
    case 2: return !c && !z;
    case 3: return c || z;
    case 4: return !c;
    case 5: return c;
    case 6: return !z;
    case 7: return z;
    case 8: return !v;
    case 9: return v;
    case 10: return !n;
    case 11: return n;
    case 12: return n == v;
    case 13: return n != v;
    case 14: return !z && n == v;
    case 15: return z || n != v;
    }
    return false;
}

void M68000::logic_flags(U32 value, Size size)
{
    const U32 width_mask = mask(size);
    value &= width_mask;
    sr &= ~(negative | zero | overflow | carry);
    if (!value)
        sr |= zero;
    if (value & ((width_mask >> 1) + 1))
        sr |= negative;
}

U32 M68000::calculate(Operation operation, U32 left, U32 right, Size size)
{
    const U32 width_mask = mask(size);
    const U32 sign = (width_mask >> 1) + 1;
    left &= width_mask;
    right &= width_mask;
    U32 result;
    switch (operation) {
    case Operation::bit_or: result = left | right; break;
    case Operation::bit_and: result = left & right; break;
    case Operation::bit_xor: result = left ^ right; break;
    case Operation::add: {
        result = (left + right) & width_mask;
        logic_flags(result, size);
        sr &= ~extend;
        if (result < left)
            sr |= carry | extend;
        if ((~(left ^ right) & (left ^ result)) & sign)
            sr |= overflow;
        return result;
    }
    case Operation::subtract:
    case Operation::compare:
        result = (left - right) & width_mask;
        logic_flags(result, size);
        if (operation == Operation::subtract) {
            sr &= ~extend;
            if (left < right)
                sr |= extend;
        }
        if (left < right)
            sr |= carry;
        if (((left ^ right) & (left ^ result)) & sign)
            sr |= overflow;
        return result;
    default: invalid();
    }
    logic_flags(result, size);
    return result;
}

void M68000::invalid() const
{
    throw CpuFault{CpuFault::Reason::instruction, instruction_pc, opcode, 0};
}

unsigned M68000::step()
{
    if (stopped)
        return 4;
    instruction_pc = pc;
    if (pc & 1)
        throw CpuFault{CpuFault::Reason::address, pc, 0, pc};
    if (bus.observe_sprites())
        bus.sprite_instruction(pc & 0xffffff, address[0], address[2], data[4], sr);
    opcode = bus.fetch_opcode(pc);
    pc += 2;
    const unsigned group = opcode >> 12;
    switch (group) {
    case 0: return immediate();
    case 1: case 2: case 3: return move(group);
    case 4: return miscellaneous();
    case 5: return quick();
    case 6: return branch();
    case 7: {
        if (opcode & 0x0100)
            invalid();
        const U32 value = signed_value(opcode, Size::byte);
        data[(opcode >> 9) & 7] = value;
        logic_flags(value, Size::longword);
        return 4;
    }
    case 8: case 9: case 11: case 12: case 13: return arithmetic(group);
    case 14: return shift();
    default: invalid();
    }
}

unsigned M68000::move(unsigned group)
{
    // An empty object list has no position to average. Preserve the previous
    // average in this specific cartridge routine and return through its epilogue.
    if (opcode == 0x3043 && bus.is_object_average(instruction_pc) && !Word(data[3])) {
        pc = instruction_pc + 20;
        return 10;
    }
    const Size size = group == 1 ? Size::byte : group == 2 ? Size::longword : Size::word;
    const unsigned dst_mode = (opcode >> 6) & 7;
    const unsigned dst_reg = (opcode >> 9) & 7;
    if (dst_mode == 7 && dst_reg > 1)
        invalid();
    const auto source = operand((opcode >> 3) & 7, opcode & 7, size);
    const U32 value = read(source, size);
    const auto destination = operand(dst_mode, dst_reg, size);
    write(destination, size, value);
    if (dst_mode != 1)
        logic_flags(value, size);
    return 4 + source.cycles + destination.cycles - (dst_mode == 4 ? 2 : 0);
}

unsigned M68000::branch()
{
    const unsigned code = (opcode >> 8) & 15;
    const U32 base = pc;
    const bool short_branch = opcode & 255;
    const U32 displacement = short_branch ? signed_value(opcode, Size::byte)
                                           : signed_value(fetch(), Size::word);
    if (code == 1) {
        push(pc, Size::longword);
        pc = base + displacement;
        return 18;
    }
    if (condition(code)) {
        pc = base + displacement;
        return 10;
    }
    return short_branch ? 8 : 12;
}

unsigned M68000::bit_instruction(bool dynamic)
{
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    const unsigned type = (opcode >> 6) & 3;
    if (mode == 1 || (mode == 7 && reg > (type ? 1 : 4)))
        invalid();
    const Size size = mode == 0 ? Size::longword : Size::byte;
    const unsigned index = dynamic ? data[(opcode >> 9) & 7] : fetch();
    const auto destination = operand(mode, reg, size);
    const U32 bit = U32{1} << (index & (mode == 0 ? 31 : 7));
    const U32 value = read(destination, size);
    sr = (sr & ~zero) | ((value & bit) ? 0 : zero);
    if (type != 0) {
        const U32 result = type == 1 ? value ^ bit : type == 2 ? value & ~bit : value | bit;
        write(destination, size, result);
    }
    return (dynamic ? 6 : 10) + destination.cycles + (type ? 2 : 0);
}

unsigned M68000::immediate()
{
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    if ((opcode & 0xf138) == 0x0108) {
        const U32 location = address[reg] + signed_value(fetch(), Size::word);
        const unsigned data_reg = (opcode >> 9) & 7;
        const unsigned count = (opcode & 0x40) ? 4 : 2;
        if (opcode & 0x80) {
            for (unsigned i = 0; i < count; ++i)
                bus.write8(location + i * 2, Byte(data[data_reg] >> ((count - i - 1) * 8)));
        } else {
            U32 value = 0;
            for (unsigned i = 0; i < count; ++i)
                value = (value << 8) | bus.read8(location + i * 2);
            write({Kind::data, data_reg, 0}, count == 4 ? Size::longword : Size::word, value);
        }
        return count == 4 ? 24 : 16;
    }
    if (opcode & 0x0100)
        return bit_instruction(true);
    if ((opcode & 0x0f00) == 0x0800)
        return bit_instruction(false);

    const unsigned kind = (opcode >> 8) & 15;
    Operation operation;
    switch (kind) {
    case 0: operation = Operation::bit_or; break;
    case 2: operation = Operation::bit_and; break;
    case 4: operation = Operation::subtract; break;
    case 6: operation = Operation::add; break;
    case 10: operation = Operation::bit_xor; break;
    case 12: operation = Operation::compare; break;
    default: invalid();
    }
    const Size size = size_field((opcode >> 6) & 3);
    if ((opcode & 63) == 60 && (kind == 0 || kind == 2 || kind == 10)) {
        if (size == Size::longword)
            invalid();
        if (size == Size::word)
            require_supervisor();
        const Word value = Word(fetch_immediate(size));
        const Word result = kind == 0 ? sr | value : kind == 2 ? sr & value : sr ^ value;
        status(size == Size::word ? result : (sr & 0xff00) | (result & 31));
        return 20;
    }
    if (mode == 1 || (mode == 7 && reg > 1))
        invalid();
    const U32 value = fetch_immediate(size);
    const auto destination = operand(mode, reg, size);
    const U32 result = calculate(operation, read(destination, size), value, size);
    if (operation != Operation::compare)
        write(destination, size, result);
    return (size == Size::longword ? 16 : 8) + destination.cycles + (mode >= 2 && kind != 12 ? 4 : 0);
}

unsigned M68000::quick()
{
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    const unsigned code = (opcode >> 8) & 15;
    if ((opcode & 0x00c0) == 0x00c0) {
        if (mode == 1) {
            const U32 base = pc;
            const U32 displacement = signed_value(fetch(), Size::word);
            if (condition(code))
                return 12;
            const Word counter = Word(data[reg] - 1);
            data[reg] = (data[reg] & 0xffff0000) | counter;
            if (counter != 0xffff) {
                pc = base + displacement;
                return 10;
            }
            return 14;
        }
        if (mode == 7 && reg > 1)
            invalid();
        const auto destination = operand(mode, reg, Size::byte);
        const bool enabled = condition(code);
        write(destination, Size::byte, enabled ? 255 : 0);
        return (mode ? 8 : (enabled ? 6 : 4)) + destination.cycles;
    }
    const Size size = size_field((opcode >> 6) & 3);
    const unsigned field = (opcode >> 9) & 7;
    const unsigned amount = field ? field : 8;
    const bool sub = opcode & 0x100;
    if (mode == 1) {
        if (size == Size::byte)
            invalid();
        address[reg] += sub ? -amount : amount;
        return 8;
    }
    if (mode == 7 && reg > 1)
        invalid();
    const auto destination = operand(mode, reg, size);
    const U32 value = read(destination, size);
    write(destination, size, calculate(sub ? Operation::subtract : Operation::add, value, amount, size));
    return (mode || size == Size::longword ? 8 : 4) + destination.cycles;
}

unsigned M68000::move_multiple()
{
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    const bool load = opcode & 0x0400;
    const Size size = (opcode & 0x40) ? Size::longword : Size::word;
    if (mode < 2 || (mode == 3 && !load) || (mode == 4 && load) ||
        (mode == 7 && reg > (load ? 3 : 1)))
        invalid();
    const Word list = fetch();
    const U32 start = mode == 3 || mode == 4 ? address[reg] : operand(mode, reg, size).value;
    U32 location = start;
    for (unsigned index = 0; index < 16; ++index) {
        if (!(list & (1u << index)))
            continue;
        const unsigned selected = mode == 4 ? 15 - index : index;
        U32 &value = selected < 8 ? data[selected] : address[selected - 8];
        if (mode == 4)
            location -= bytes(size);
        if (load)
            value = signed_value(read_memory(location, size), size);
        else
            write_memory(location, size, value);
        if (mode != 4)
            location += bytes(size);
    }
    if (mode == 3 || mode == 4)
        address[reg] = location;
    const unsigned extension_cycles = mode == 5 ? 4 : mode == 6 ? 6 :
        mode == 7 ? (reg == 1 ? 8 : reg == 3 ? 6 : 4) : 0;
    return (load ? 12 : 8) + extension_cycles +
           std::popcount(list) * (size == Size::word ? 4 : 8);
}

unsigned M68000::miscellaneous()
{
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    if ((opcode & 0xfff0) == 0x4e40) {
        exception(32 + (opcode & 15));
        return 34;
    }
    if ((opcode & 0xfff8) == 0x4e50) {
        const U32 displacement = signed_value(fetch(), Size::word);
        push(address[reg], Size::longword);
        address[reg] = address[7];
        address[7] += displacement;
        return 16;
    }
    if ((opcode & 0xfff8) == 0x4e58) {
        address[7] = address[reg];
        const U32 value = pop(Size::longword);
        address[reg] = value;
        return 12;
    }
    if ((opcode & 0xfff0) == 0x4e60) {
        require_supervisor();
        if (opcode & 8)
            address[reg] = user_stack;
        else
            user_stack = address[reg];
        return 4;
    }
    switch (opcode) {
    case 0x4e71: return 4;
    case 0x4e72:
        require_supervisor();
        status(fetch());
        stopped = true;
        return 4;
    case 0x4e73: {
        require_supervisor();
        const Word previous = Word(pop(Size::word));
        pc = pop(Size::longword);
        status(previous);
        return 20;
    }
    case 0x4e75:
        pc = pop(Size::longword);
        return 16;
    case 0x4e76:
        if (sr & overflow) {
            exception(7);
            return 34;
        }
        return 4;
    case 0x4e77: {
        const auto flags = pop(Size::word) & 31;
        sr = (sr & ~31) | flags;
        pc = pop(Size::longword);
        return 20;
    }
    default: break;
    }

    if ((opcode & 0xffb8) == 0x4880) {
        const Size source = (opcode & 0x40) ? Size::word : Size::byte;
        const Size result = (opcode & 0x40) ? Size::longword : Size::word;
        const U32 value = signed_value(data[reg], source);
        write({Kind::data, reg, 0}, result, value);
        logic_flags(value, result);
        return 4;
    }
    if ((opcode & 0xfb80) == 0x4880)
        return move_multiple();

    const bool lea = (opcode & 0xf1c0) == 0x41c0;
    const bool jump = (opcode & 0xff80) == 0x4e80;
    const bool pea = (opcode & 0xffc0) == 0x4840;
    if (pea && mode == 0) {
        data[reg] = std::rotl(data[reg], 16);
        logic_flags(data[reg], Size::longword);
        return 4;
    }
    if (lea || jump || pea) {
        if (mode < 2 || mode == 3 || mode == 4 || (mode == 7 && reg > 3))
            invalid();
        const auto target = operand(mode, reg, Size::word);
        if (lea) {
            address[(opcode >> 9) & 7] = target.value;
            return target.cycles + (mode == 6 || (mode == 7 && reg == 3) ? 2 : 0);
        }
        if (pea) {
            push(target.value, Size::longword);
            return 8 + target.cycles + (mode == 6 || (mode == 7 && reg == 3) ? 2 : 0);
        }
        const bool call = !(opcode & 64);
        if (call)
            push(pc, Size::longword);
        pc = target.value;
        const unsigned overhead = mode == 2 ? 0 : mode == 6 || (mode == 7 && reg == 3) ? 6 :
            (mode == 7 && reg == 1) ? 4 : 2;
        return (call ? 16 : 8) + overhead;
    }

    const unsigned status_op = opcode & 0xffc0;
    if (status_op == 0x40c0 || status_op == 0x44c0 || status_op == 0x46c0) {
        if (mode == 1 || (mode == 7 && reg > (status_op == 0x40c0 ? 1 : 4)))
            invalid();
        if (status_op == 0x46c0)
            require_supervisor();
        const auto target = operand(mode, reg, Size::word);
        if (status_op == 0x40c0) {
            write(target, Size::word, sr);
            return (mode ? 8 : 6) + target.cycles;
        }
        const Word value = Word(read(target, Size::word));
        status(status_op == 0x44c0 ? (sr & 0xff00) | (value & 31) : value);
        return 12 + target.cycles;
    }

    const unsigned kind = opcode & 0xff00;
    if (mode == 1 || (mode == 7 && reg > 1))
        invalid();
    if (status_op == 0x4ac0) {
        const auto target = operand(mode, reg, Size::byte);
        const U32 value = read(target, Size::byte);
        logic_flags(value, Size::byte);
        write(target, Size::byte, value | 128);
        return (mode ? 10 : 4) + target.cycles;
    }
    if (kind != 0x4000 && kind != 0x4200 && kind != 0x4400 && kind != 0x4600 && kind != 0x4a00)
        invalid();
    const Size size = size_field((opcode >> 6) & 3);
    const auto target = operand(mode, reg, size);
    const U32 value = read(target, size);
    U32 result = 0;
    switch (kind) {
    case 0x4000: {
        const U32 x = (sr & extend) != 0;
        const Word previous = sr;
        result = calculate(Operation::subtract, 0, value, size) - x;
        logic_flags(result, size);
        sr &= ~(carry | extend);
        if (value || x)
            sr |= carry | extend;
        if (!(previous & zero))
            sr &= ~zero;
        if (value == ((mask(size) >> 1) + 1) && !x)
            sr |= overflow;
        break;
    }
    case 0x4200: logic_flags(0, size); break;
    case 0x4400: result = calculate(Operation::subtract, 0, value, size); break;
    case 0x4600: result = ~value; logic_flags(result, size); break;
    case 0x4a00: logic_flags(value, size); return 4 + target.cycles;
    }
    write(target, size, result);
    return (mode ? (size == Size::longword ? 12 : 8) : size == Size::longword ? 6 : 4) + target.cycles;
}

unsigned M68000::arithmetic(unsigned group)
{
    const unsigned data_reg = (opcode >> 9) & 7;
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    const unsigned opmode = (opcode >> 6) & 7;

    if ((group == 8 || group == 12) && (opcode & 0x01f0) == 0x0100) {
        const bool memory = opcode & 8;
        const auto source = operand(memory ? 4 : 0, reg, Size::byte);
        const int right = read(source, Size::byte);
        const auto destination = operand(memory ? 4 : 0, data_reg, Size::byte);
        const int left = read(destination, Size::byte);
        const int x = (sr & extend) != 0;
        int result;
        bool carry_out;
        if (group == 12) {
            result = left + right + x;
            if ((left & 15) + (right & 15) + x > 9)
                result += 6;
            carry_out = result > 0x99;
            if (carry_out)
                result += 0x60;
        } else {
            const int binary = left - right - x;
            result = binary;
            if ((left & 15) < (right & 15) + x)
                result -= 6;
            carry_out = binary < 0;
            if (carry_out)
                result -= 0x60;
        }
        sr &= ~(carry | extend);
        if (carry_out)
            sr |= carry | extend;
        if (Byte(result))
            sr &= ~zero;
        write(destination, Size::byte, Byte(result));
        return memory ? 18 : 6;
    }

    if (group == 12) {
        switch (opcode & 0xf1f8) {
        case 0xc140: std::swap(data[data_reg], data[reg]); return 6;
        case 0xc148: std::swap(address[data_reg], address[reg]); return 6;
        case 0xc188: std::swap(data[data_reg], address[reg]); return 6;
        }
    }

    if (opmode == 3 || opmode == 7) {
        if (group == 8 || group == 12) {
            if (mode == 1)
                invalid();
            const auto source = operand(mode, reg, Size::word);
            const U32 right = read(source, Size::word);
            if (group == 12) {
                const U32 left = Word(data[data_reg]);
                data[data_reg] = opmode == 3 ? left * right :
                    signed_value(left, Size::word) * signed_value(right, Size::word);
                logic_flags(data[data_reg], Size::longword);
                return 70 + source.cycles;
            }
            if (!right) {
                exception(5);
                return 38 + source.cycles;
            }
            if (opmode == 3) {
                const U32 quotient = data[data_reg] / right;
                if (quotient <= 65535) {
                    const U32 remainder = data[data_reg] % right;
                    data[data_reg] = (remainder << 16) | quotient;
                    logic_flags(quotient, Size::word);
                    return 140 + source.cycles;
                }
            } else {
                const std::int64_t dividend = std::bit_cast<std::int32_t>(data[data_reg]);
                const int divisor = std::bit_cast<std::int16_t>(Word(right));
                const auto quotient = dividend / divisor;
                if (quotient >= -32768 && quotient <= 32767) {
                    data[data_reg] = (U32(Word(dividend % divisor)) << 16) | Word(quotient);
                    logic_flags(Word(quotient), Size::word);
                    return 158 + source.cycles;
                }
            }
            sr = (sr & ~(carry | zero)) | overflow | negative;
            return (opmode == 3 ? 140 : 158) + source.cycles;
        }
        const Size size = opmode == 3 ? Size::word : Size::longword;
        const auto source = operand(mode, reg, size);
        const U32 value = signed_value(read(source, size), size);
        if (group == 9)
            address[data_reg] -= value;
        else if (group == 13)
            address[data_reg] += value;
        else
            calculate(Operation::compare, address[data_reg], value, Size::longword);
        return (group == 11 || size == Size::longword ? 6 : 8) + source.cycles;
    }

    const bool to_ea = opmode >= 4;
    const Size size = size_field(opmode & 3);
    if (group == 11 && to_ea && mode == 1) {
        const auto source = operand(3, reg, size);
        const U32 right = read(source, size);
        const auto destination = operand(3, data_reg, size);
        calculate(Operation::compare, read(destination, size), right, size);
        return size == Size::longword ? 20 : 12;
    }
    if (to_ea && (group == 9 || group == 13) && mode < 2) {
        const auto source = operand(mode ? 4 : 0, reg, size);
        const U32 right = read(source, size);
        const auto destination = operand(mode ? 4 : 0, data_reg, size);
        const U32 left = read(destination, size);
        const unsigned x = (sr & extend) != 0;
        const U32 width_mask = mask(size);
        const U32 sign = (width_mask >> 1) + 1;
        const bool sub = group == 9;
        const U32 result = (sub ? left - right - x : left + right + x) & width_mask;
        const bool carry_out = sub ? std::uint64_t(left) < std::uint64_t(right) + x :
            std::uint64_t(left) + right + x > width_mask;
        const bool overflow_out = sub ? ((left ^ right) & (left ^ result) & sign) != 0 :
            (~(left ^ right) & (left ^ result) & sign) != 0;
        const Word previous = sr;
        logic_flags(result, size);
        if (!(previous & zero))
            sr &= ~zero;
        sr &= ~extend;
        if (carry_out)
            sr |= carry | extend;
        if (overflow_out)
            sr |= overflow;
        write(destination, size, result);
        return mode ? (size == Size::longword ? 30 : 18) : (size == Size::longword ? 8 : 4);
    }
    if ((mode == 1 && (to_ea || group == 8 || group == 12)) ||
        (to_ea && mode == 7 && reg > 1) ||
        (to_ea && mode == 0 && group != 11))
        invalid();

    const auto ea = operand(mode, reg, size);
    const Operand dn{Kind::data, data_reg, 0};
    const Operand source = to_ea ? dn : ea;
    const Operand destination = to_ea ? ea : dn;
    Operation operation;
    switch (group) {
    case 8: operation = Operation::bit_or; break;
    case 9: operation = Operation::subtract; break;
    case 11: operation = to_ea ? Operation::bit_xor : Operation::compare; break;
    case 12: operation = Operation::bit_and; break;
    case 13: operation = Operation::add; break;
    default: invalid();
    }
    const U32 right = read(source, size);
    const U32 result = calculate(operation, read(destination, size), right, size);
    if (operation != Operation::compare)
        write(destination, size, result);
    const unsigned base = to_ea && mode ? (size == Size::longword ? 12 : 8) :
        (size == Size::longword ? 6 : 4);
    return base + ea.cycles;
}

unsigned M68000::shift()
{
    const bool memory = (opcode & 0x00c0) == 0x00c0;
    const unsigned mode = (opcode >> 3) & 7, reg = opcode & 7;
    if (memory && ((opcode & 0x0800) || mode < 2 || (mode == 7 && reg > 1)))
        invalid();
    const bool left = opcode & 0x100;
    const Size size = memory ? Size::word : size_field((opcode >> 6) & 3);
    const unsigned kind = memory ? (opcode >> 9) & 3 : (opcode >> 3) & 3;
    const unsigned count_field = (opcode >> 9) & 7;
    const unsigned count = memory ? 1 : (opcode & 32) ? data[count_field] & 63 :
        count_field ? count_field : 8;
    const auto target = operand(memory ? mode : 0, reg, size);
    const U32 width_mask = mask(size);
    const U32 sign = (width_mask >> 1) + 1;
    U32 value = read(target, size);
    bool x = sr & extend;
    bool last = kind == 2 && x;
    bool changed_sign = false;
    for (unsigned i = 0; i < count; ++i) {
        const bool old_sign = value & sign;
        last = left ? old_sign : (value & 1);
        if (left) {
            value = (value << 1) & width_mask;
            value |= kind == 2 ? x : kind == 3 && last;
        } else {
            value >>= 1;
            if ((kind == 0 && old_sign) || (kind == 2 && x) || (kind == 3 && last))
                value |= sign;
        }
        if (kind != 3)
            x = last;
        if (kind == 0 && left && old_sign != ((value & sign) != 0))
            changed_sign = true;
    }
    logic_flags(value, size);
    sr &= ~extend;
    if (x)
        sr |= extend;
    if (last)
        sr |= carry;
    if (changed_sign)
        sr |= overflow;
    write(target, size, value);
    return memory ? 8 + target.cycles : (size == Size::longword ? 8 : 6) + count * 2;
}

} // namespace markv
