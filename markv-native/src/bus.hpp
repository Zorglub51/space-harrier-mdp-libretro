#pragma once

#include "fm_ports.hpp"
#include "psg.hpp"
#include "scene_sprites.hpp"
#include "timing.hpp"
#include "video.hpp"

#include <vector>

namespace markv {

struct AudioLevels {
    unsigned fm = 100, pcm = 100, psg = 100;
    bool operator==(const AudioLevels &) const = default;
};

class Bus {
public:
    explicit Bus(std::span<const Byte> cartridge);
    Bus(const Bus &) = delete;
    Bus &operator=(const Bus &) = delete;

    Byte read8(std::uint32_t address);
    Word read16(std::uint32_t address);
    std::uint32_t read32(std::uint32_t address);
    void write8(std::uint32_t address, Byte value);
    void write16(std::uint32_t address, Word value);
    void write32(std::uint32_t address, std::uint32_t value);

    void begin_line(unsigned slice);
    unsigned interrupt_level() const;
    void acknowledge(unsigned level);
    void advance(unsigned cycles)
    {
        fm.advance(cycles);
        audio_cycles += cycles;
        if (audio_cycles >= cycles_per_sample)
            render_audio();
    }
    void begin_audio() { audio_size = 0; }
    std::span<const std::int16_t> audio() const { return {audio_frame.data(), audio_size}; }
    void set_audio_levels(AudioLevels levels);
    void set_video_options(bool widescreen, bool mark_vi);
    bool supports_video_options() const { return game_profile != 0; }
    bool widescreen() const { return wide_video; }
    bool mark_vi() const { return extended_sprites; }
    bool observe_sprites() const { return extended_sprites; }
    void sprite_instruction(unsigned pc, unsigned a0, unsigned a2, unsigned d4, Word status)
    {
        switch (pc >> 12) {
        case 0x13b: case 0x16d: case 0x170: case 0x179: case 0x1dd:
            scene_sprites.instruction(*this, game_profile, pc, a0, a2, d4, status);
        }
    }
    SpriteList scene() const { return scene_sprites.displayed((video.reg[5] & 127) * 512); }
    bool z80_in_reset() const { return sound_reset; }
    bool z80_has_bus() const { return !sound_bus_requested; }
    bool z80_irq() const { return video_line == -38; }
    Byte z80_read(Word address);
    void z80_write(Word address, Byte value);
    void buttons(Byte active_low) { pad = active_low; }
    bool is_object_average(unsigned pc) const { return pc == object_average_pc; }
    Word fetch_opcode(std::uint32_t address)
    {
        address &= 0xffffff;
        return address < 0x400000 ? instruction_rom[(address >> 1) & rom_mask] : read16(address);
    }

    Video video;

private:
    Word read_port(unsigned offset);
    void control(Word value);
    void write_data(Word value);
    void write_vscroll(unsigned index, Word value);
    void set_vram_byte(Word address, Byte value);
    void transfer();
    Word read_dma(std::uint32_t source);
    void render_audio();

    std::vector<Word> rom;
    std::vector<Word> rom_with_hooks;
    const Word *instruction_rom = nullptr;
    std::array<Word, 65536> work_ram{};
    std::array<Byte, 8192> sound_ram{};
    FmPorts fm;
    Psg psg;
    AudioLevels audio_levels;
    std::array<std::int16_t, 2 * (ticks_per_frame / ticks_per_sample + 4)> audio_frame{};
    std::array<int, 2> audio_dc{};
    unsigned audio_cycles = 0, audio_size = 0;
    std::array<Byte, 3> io_data{0x40, 0x40, 0x40}, io_control{};
    unsigned rom_mask = 0;
    Byte pad = 0xff;
    Word video_address = 0;
    unsigned command = 0xff, h_counter = 0;
    int video_line = -38;
    bool second_control = false, horizontal_irq = false, vertical_irq = false;
    unsigned z80_bank = 0;
    bool sound_bus_requested = false, sound_reset = true;
    unsigned object_average_pc = 0xffffffff;
    unsigned game_profile = 0;
    bool wide_video = false, extended_sprites = false;
    SceneSprites scene_sprites;
};

} // namespace markv
