#pragma once

#include "bus.hpp"

namespace markv {

struct CpuFault {
    enum class Reason { instruction, address, privilege } reason;
    std::uint32_t pc;
    Word opcode;
    std::uint32_t address;
};

class M68000 {
public:
    explicit M68000(Bus &bus) : bus(bus) {}

    void reset();
    unsigned step();
    unsigned interrupt(unsigned level);

    std::array<std::uint32_t, 8> data{}, address{};
    std::uint32_t pc = 0;
    Word sr = 0;
    bool stopped = false;

private:
    enum class Size : unsigned { byte = 1, word = 2, longword = 4 };
    enum class Kind { data, address, memory, immediate };
    struct Operand { Kind kind; std::uint32_t value; unsigned cycles; };
    enum class Operation { bit_or, bit_and, subtract, add, bit_xor, compare };

    static constexpr Word carry = 1, overflow = 2, zero = 4, negative = 8, extend = 16;
    static constexpr Word supervisor = 0x2000;

    Word fetch();
    std::uint32_t fetch_immediate(Size size);
    std::uint32_t read_memory(std::uint32_t location, Size size);
    void write_memory(std::uint32_t location, Size size, std::uint32_t value);
    Operand operand(unsigned mode, unsigned reg, Size size);
    std::uint32_t read(Operand source, Size size);
    void write(Operand destination, Size size, std::uint32_t value);
    std::uint32_t indexed(std::uint32_t base);
    void push(std::uint32_t value, Size size);
    std::uint32_t pop(Size size);
    void status(Word value);
    void exception(unsigned vector);
    void require_supervisor() const;
    bool condition(unsigned code) const;
    static unsigned bytes(Size size) { return unsigned(size); }
    static std::uint32_t mask(Size size);
    static std::uint32_t signed_value(std::uint32_t value, Size size);
    Size size_field(unsigned value) const;
    void logic_flags(std::uint32_t value, Size size);
    std::uint32_t calculate(Operation operation, std::uint32_t left, std::uint32_t right, Size size);
    [[noreturn]] void invalid() const;

    unsigned move(unsigned group);
    unsigned immediate();
    unsigned miscellaneous();
    unsigned quick();
    unsigned branch();
    unsigned arithmetic(unsigned group);
    unsigned shift();
    unsigned bit_instruction(bool dynamic);
    unsigned move_multiple();

    Bus &bus;
    std::uint32_t user_stack = 0, supervisor_stack = 0, instruction_pc = 0;
    Word opcode = 0;
};

} // namespace markv
