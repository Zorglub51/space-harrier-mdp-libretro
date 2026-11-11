#include "bus.hpp"
#include "rom_profile.hpp"

#include <algorithm>
#include <bit>
#include <stdexcept>

namespace markv {
namespace {

constexpr unsigned address_mask = 0xffffff;
constexpr unsigned video_base = 0xc00000;
constexpr unsigned ram_base = 0xe00000;
constexpr unsigned rom_end = 0x400000;

struct ObjectAverageRoutine {
    unsigned start;
    std::array<Word, 12> signature;
};

constexpr ObjectAverageRoutine object_average_routines[] = {
    {0x17264a, {0x3043, 0x2f08, 0x2f00, 0x4eb9, 0x001f, 0xabcc, 0x508f, 0x23c0, 0x00ff, 0x3bf0, 0x4cdf, 0x7cfc}},
    {0x13d35c, {0x3043, 0x2f08, 0x2f00, 0x4eb9, 0x001a, 0x9bcc, 0x508f, 0x23c0, 0x00ff, 0x2e70, 0x4cdf, 0x7cfc}},
};

Byte lane(Word word, unsigned address)
{
    return Byte(word >> ((address & 1) ? 0 : 8));
}

Word merge(Word word, unsigned address, Byte value)
{
    return (address & 1) ? Word((word & 0xff00) | value) : Word((word & 255) | (value << 8));
}

} // namespace

Bus::Bus(std::span<const Byte> cartridge)
{
    if (cartridge.size() < 8 || cartridge.size() > rom_end)
        throw std::invalid_argument("cartridge length outside the Mark V ROM window");
    rom.resize(std::bit_ceil((cartridge.size() + 1) / 2), 0xffff);
    rom_mask = rom.size() - 1;
    for (unsigned index = 0; index < cartridge.size(); ++index)
        rom[index >> 1] = merge(rom[index >> 1], index, cartridge[index]);

    instruction_rom = rom.data();
    if (cartridge.size() >= 0x8000) {
        std::uint32_t profile = 0;
        for (unsigned word = 0; word < 0x4000; word += 2)
            profile += (std::uint32_t(rom[word]) << 16) | rom[word + 1];
        const auto hooks = guest_opcodes(cartridge.size(), profile);
        if (!hooks.empty()) {
            for (const auto &hook : hooks) {
                const Word word = rom[hook.pc / 2];
                if (word != hook.encoded && word != hook.decoded)
                    throw std::invalid_argument("Mark V ROM profile does not match the native-hook addresses");
            }
            rom_with_hooks = rom;
            for (const auto &hook : hooks)
                rom_with_hooks[hook.pc / 2] = hook.decoded;
            instruction_rom = rom_with_hooks.data();
            game_profile = cartridge.size() == 0x3e0000 ? 1 : 2;
            for (const auto &routine : object_average_routines) {
                if (std::equal(routine.signature.begin(), routine.signature.end(), rom.begin() + routine.start / 2)) {
                    object_average_pc = routine.start;
                    break;
                }
            }
        }
    }
}

Word Bus::read16(std::uint32_t address)
{
    address &= address_mask;
    if (address < rom_end)
        return rom[(address >> 1) & rom_mask];
    if (address >= ram_base)
        return work_ram[(address >> 1) & 65535];
    if (address >= 0xd00000 && address < 0xd20000)
        return video.vram[(address >> 1) & 65535];
    if (address >= video_base && address < video_base + 0x800)
        return read_port(address - video_base);
    if (address == 0xa11100)
        return sound_bus_requested ? 0 : 0x0100;
    return Word((unsigned(read8(address)) << 8) | read8(address + 1));
}

Byte Bus::read8(std::uint32_t address)
{
    address &= address_mask;
    if (address < rom_end)
        return lane(rom[(address >> 1) & rom_mask], address);
    if (address >= ram_base)
        return lane(work_ram[(address >> 1) & 65535], address);
    if (address >= 0xd00000 && address < 0xd20000)
        return lane(video.vram[(address >> 1) & 65535], address);
    if (address >= video_base && address < video_base + 0x800)
        return lane(read_port((address - video_base) & ~1u), address);
    if ((address & ~1u) == 0xa11100)
        return lane(sound_bus_requested ? 0 : 0x0100, address);
    if (address >= 0xa04000 && address < 0xa04004)
        return fm.status();
    if (address >= 0xa00000 && address < 0xa10000 && sound_bus_requested)
        return z80_read(Word(address));
    if (address == 0xa10001)
        return 0x20;
    if (address >= 0xa10003 && address <= 0xa10007) {
        const unsigned port = (address - 0xa10002) / 2;
        Byte inputs = 0x7f;
        if (port == 0) {
            inputs = (io_data[port] & 64)
                ? Byte((pad & 63) | 64)
                : Byte((pad & 3) | ((pad >> 2) & 48));
        }
        return (inputs & ~io_control[port]) | (io_data[port] & io_control[port]);
    }
    if (address >= 0xa10009 && address <= 0xa1000d)
        return io_control[(address - 0xa10008) / 2];
    return 0xff;
}

std::uint32_t Bus::read32(std::uint32_t address)
{
    const Word high = read16(address);
    return (std::uint32_t(high) << 16) | read16(address + 2);
}

void Bus::write8(std::uint32_t address, Byte value)
{
    address &= address_mask;
    if (address >= ram_base) {
        auto &word = work_ram[(address >> 1) & 65535];
        word = merge(word, address, value);
    } else if ((address & ~6u) == 0xc00011) {
        psg.write(value);
    } else if ((address >= video_base && address < video_base + 0x800) ||
               (address >= 0xd00000 && address < 0xd20000)) {
        write16(address & ~1u, Word(value * 257));
    } else if (address >= 0xa04000 && address < 0xa04004) {
        fm.write(address & 3, value);
    } else if (address >= 0xa00000 && address < 0xa10000 && sound_bus_requested) {
        z80_write(Word(address), value);
    } else if (address == 0xa11100) {
        sound_bus_requested = value & 1;
    } else if (address == 0xa11200) {
        sound_reset = !(value & 1);
        if (sound_reset)
            z80_bank = 0;
    } else if (address >= 0xa10003 && address <= 0xa10007 && (address & 1)) {
        io_data[(address - 0xa10003) / 2] = value;
    } else if (address >= 0xa10009 && address <= 0xa1000d && (address & 1)) {
        io_control[(address - 0xa10009) / 2] = value;
    }
}

void Bus::write16(std::uint32_t address, Word value)
{
    address &= address_mask;
    if (address >= ram_base) {
        work_ram[(address >> 1) & 65535] = value;
    } else if (address >= 0xd00000 && address < 0xd20000) {
        if (observe_sprites())
            scene_sprites.vram_write(address - 0xd00000);
        video.vram[(address >> 1) & 65535] = value;
    } else if (address >= 0xc00100 && address < 0xc00180) {
        video.reg[(address - 0xc00100) / 2] = Byte(value);
    } else if (address >= 0xc00200 && address < 0xc00280) {
        write_vscroll((address - 0xc00200) / 2, value);
    } else if (address >= 0xc00400 && address < 0xc00500) {
        video.set_color((address - 0xc00400) / 2, value);
    } else if (address >= video_base && address < video_base + 8) {
        if (address & 4)
            control(value);
        else
            write_data(value);
    } else if ((address & ~6u) == 0xc00010) {
        psg.write(Byte(value));
    } else if (address >= video_base && address < video_base + 0x800) {
        return;
    } else {
        write8(address, Byte(value >> 8));
        write8(address + 1, Byte(value));
    }
}

void Bus::write32(std::uint32_t address, std::uint32_t value)
{
    write16(address, Word(value >> 16));
    write16(address + 2, Word(value));
}

Byte Bus::z80_read(Word address)
{
    if (address < 0x4000)
        return sound_ram[address & 8191];
    if (address < 0x4004)
        return fm.status();
    if (address >= 0x8000) {
        const unsigned mapped = (z80_bank << 15) | (address & 0x7fff);
        // A banked access cannot re-enter the Z80's own bus.
        if (mapped < 0xa00000 || mapped >= 0xa10000)
            return read8(mapped);
    }
    return 255;
}

void Bus::z80_write(Word address, Byte value)
{
    if (address < 0x4000) {
        sound_ram[address & 8191] = value;
    } else if (address < 0x4004) {
        fm.write(address & 3, value);
    } else if (address == 0x6000) {
        z80_bank = (z80_bank >> 1) | ((value & 1) << 8);
    } else if ((address & ~6u) == 0x7f11) {
        psg.write(value);
    } else if (address >= 0x8000) {
        const unsigned mapped = (z80_bank << 15) | (address & 0x7fff);
        if (mapped < 0xa00000 || mapped >= 0xa10000)
            write8(mapped, value);
    }
}

void Bus::set_audio_levels(AudioLevels levels)
{
    if (audio_levels == levels)
        return;
    audio_levels = levels;
    audio_dc = {};
}

void Bus::set_video_options(bool widescreen, bool mark_vi)
{
    if (!game_profile)
        return;
    if (extended_sprites != mark_vi)
        scene_sprites.clear();
    wide_video = widescreen;
    extended_sprites = mark_vi;
}

void Bus::render_audio()
{
    do {
        audio_cycles -= cycles_per_sample;
        const auto stereo = fm.sample(audio_levels.fm, audio_levels.pcm);
        const int psg_sample = psg.sample(ticks_per_sample);
        const int mono = audio_levels.psg == 100 ? psg_sample : psg_sample * int(audio_levels.psg) / 100;
        if (audio_size + 2 > audio_frame.size())
            continue;
        for (unsigned side = 0; side < stereo.size(); ++side) {
            const int sample = stereo[side] + mono;
            // Remove DC from held DAC values and unipolar output states.
            audio_dc[side] += sample - (audio_dc[side] >> 9);
            const int ac = sample - (audio_dc[side] >> 9);
            audio_frame[audio_size++] = std::int16_t(std::clamp(ac, -32768, 32767));
        }
    } while (audio_cycles >= cycles_per_sample);
}

Word Bus::read_port(unsigned offset)
{
    if (offset < 4) {
        Word value = 0xffff;
        if (command == 0)
            value = video.vram[video_address >> 1];
        else if (command == 4 || command == 8)
            value = video.cram[(video_address >> 1) & 127];
        video_address += video.reg[15];
        return value;
    }
    if (offset < 8)
        return 0x0200 | (video_line < 0 ? 8 : 0) | (vertical_irq ? 128 : 0);
    if (offset < 12)
        return Word(Byte(video_line < -27 ? video_line + 262 : video_line) * 256);
    if (offset >= 0x400 && offset < 0x500)
        return video.cram[(offset - 0x400) / 2];
    return 0xffff;
}

void Bus::control(Word value)
{
    if (second_control) {
        second_control = false;
        video_address = (video_address & 0x3fff) | ((value & 3) << 14);
        command = (command & 3) | ((value >> 2) & 0x3c);
        if (command & 32)
            transfer();
        return;
    }
    if ((value & 0xc000) == 0x8000) {
        video.reg[(value >> 8) & 31] = Byte(value);
        return;
    }
    video_address = (video_address & 0xc000) | (value & 0x3fff);
    command = (command & 0xfc) | (value >> 14);
    second_control = true;
}

void Bus::write_vscroll(unsigned index, Word value)
{
    index &= 63;
    video.vscroll[index] = value;
    if (index < 2)
        video.vscroll[index + 62] = value;
}

void Bus::set_vram_byte(Word address, Byte value)
{
    if (observe_sprites())
        scene_sprites.vram_write(address);
    auto &word = video.vram[address >> 1];
    word = merge(word, address ^ 1u, value);
}

void Bus::write_data(Word value)
{
    second_control = false;
    if (command == 0x21 && (video.reg[23] & 0xc0) == 0x80) {
        const unsigned length = (video.reg[20] << 8) | video.reg[19];
        const unsigned bytes = length ? (length + 1) & ~1u : 65536;
        set_vram_byte(video_address ^ 1, Byte(value));
        for (unsigned i = 0; i < bytes; ++i) {
            set_vram_byte(video_address, Byte(value >> 8));
            video_address += video.reg[15];
        }
        command = 0xff;
        return;
    }
    switch (command) {
    case 1:
        if (observe_sprites())
            scene_sprites.vram_write(video_address);
        if (video_address & 1)
            value = Word((value << 8) | (value >> 8));
        video.vram[video_address >> 1] = value;
        break;
    case 3:
        video.set_color((video_address >> 1) & 127, value);
        break;
    case 5:
        write_vscroll(video_address >> 1, value);
        break;
    default:
        return;
    }
    video_address += video.reg[15];
}

Word Bus::read_dma(std::uint32_t source)
{
    if (source >= ram_base)
        return work_ram[(source >> 1) & 65535];
    return read16(source);
}

void Bus::transfer()
{
    const unsigned length = (video.reg[20] << 8) | video.reg[19];
    unsigned source = (video.reg[22] << 8) | video.reg[21];
    if (video.reg[23] & 128) {
        if (command != 0x30)
            return;
        for (unsigned i = 0; i < length; ++i, ++source) {
            const Word from = Word(source);
            const Byte value = lane(video.vram[from >> 1], from);
            set_vram_byte(video_address ^ 1, value);
            video_address += video.reg[15];
        }
        command = 0xff;
        return;
    }
    if (command != 0x21 && command != 0x23 && command != 0x25)
        return;
    source = (source | ((video.reg[23] & 127) << 16)) * 2;
    Word destination = video_address;
    if (observe_sprites() && command == 0x21 && !(destination & 1))
        scene_sprites.upload(*this, game_profile, source, destination, length, video.reg[15]);
    for (unsigned i = 0; i < length; ++i, source += 2) {
        const Word value = read_dma(source);
        if (destination & 1)
            return;
        if (command == 0x21)
            video.vram[destination >> 1] = value;
        else if (command == 0x23)
            video.set_color((destination >> 1) & 127, value);
        else
            write_vscroll(destination >> 1, value);
        destination += video.reg[15];
    }
    video_address = destination;
    video.reg[19] = 0;
    video.reg[20] = 0;
}

void Bus::begin_line(unsigned slice)
{
    video_line = int(slice) - 38;
    if (slice == 0)
        vertical_irq = true;
    if (video_line < 0) {
        horizontal_irq = false;
        h_counter = video.reg[10];
        return;
    }
    if (video_line == 0)
        vertical_irq = false;
    horizontal_irq = h_counter == 0;
    if (horizontal_irq)
        h_counter = video.reg[10];
    else
        --h_counter;
}

unsigned Bus::interrupt_level() const
{
    if (vertical_irq && (video.reg[1] & 32))
        return 6;
    if (horizontal_irq && (video.reg[0] & 16))
        return 4;
    return 0;
}

void Bus::acknowledge(unsigned level)
{
    if (level == 6)
        vertical_irq = false;
    else if (level == 4)
        horizontal_irq = false;
}

} // namespace markv
