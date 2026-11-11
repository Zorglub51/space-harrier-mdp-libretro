#pragma once

#include <cstdint>
#include <span>

namespace markv {

// Values observed in the SH1/SH2 native-hook audit. They describe guest
// instructions, so the interpreter still owns their behavior and timing.
struct GuestOpcode {
    unsigned pc;
    std::uint16_t encoded, decoded;
};

std::span<const GuestOpcode> guest_opcodes(unsigned bytes, std::uint32_t profile);

} // namespace markv
