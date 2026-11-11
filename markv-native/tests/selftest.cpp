#include "machine.hpp"
#include "interpolation.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <initializer_list>
#include <iostream>

using namespace markv;

namespace {

void require(bool pass, const char *message)
{
    if (!pass) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

using Cartridge = std::array<Byte, 512>;

void write_words(Cartridge &cartridge, unsigned address, std::initializer_list<Word> words)
{
    for (Word word : words) {
        cartridge[address++] = Byte(word >> 8);
        cartridge[address++] = Byte(word);
    }
}

Cartridge cartridge()
{
    Cartridge rom{};
    write_words(rom, 0, {0x00ff, 0xfe00, 0, 0x0100});
    write_words(rom, 30 * 4, {0, 0x0180});
    write_words(rom, 0x100, {
        0x33fc, 0x8160, 0x00c0, 0x0004,  // MOVE.W #$8160,$C00004
        0x33fc, 0x0081, 0x00c0, 0x0118,  // MOVE.W #$81,$C00118
        0x33fc, 0x000e, 0x00c0, 0x0400,  // MOVE.W #$E,$C00400
        0x23fc, 0x1234, 0x5678, 0x00ff, 0x0000,
        0x7003, 0x7200, 0x5281, 0x51c8, 0xfffc,  // MOVEQ, ADDQ.L, DBRA
        0x4e72, 0x2000, 0x60fa,  // STOP and wait for next VBlank
    });
    write_words(rom, 0x180, {0x5279, 0x00ff, 0x0020, 0x4e73});
    return rom;
}

void command(Bus &bus, Word address, unsigned code)
{
    bus.write16(0xc00004, ((code & 3) << 14) | (address & 0x3fff));
    bus.write16(0xc00004, ((code & 0x3c) << 2) | (address >> 14));
}

void test_bus()
{
    Bus bus(cartridge());
    bus.write32(0xfe0000, 0xabcd1234);
    bus.write16(0xff0000, 0x9988);
    require(bus.read32(0xe00000) == 0xabcd1234, "128 KiB RAM mirroring");
    require(bus.read16(0xff0000) == 0x9988 && bus.read8(0xfe0001) == 0xcd,
            "RAM banks and byte lanes");
    bus.write8(0xd10000, 0xa5);
    require(bus.read16(0xd10000) == 0xa5a5 && bus.read16(0xd00000) == 0,
            "independent upper VRAM and byte replication");
    bus.write8(0xc00201, 0x9c);
    require(bus.video.vscroll[0] == 0x9c9c && bus.video.vscroll[62] == 0x9c9c,
            "direct VSRAM mirror");

    bus.video.reg[15] = 2;
    bus.video.reg[19] = 2;
    bus.video.reg[23] = 0x7f;
    command(bus, 0, 0x21);
    require(bus.video.vram[0] == 0xabcd && bus.video.vram[1] == 0x1234 &&
            bus.video.reg[19] == 0 && bus.video.reg[23] == 0x7f,
            "two-word DMA and source preservation");
    bus.video.reg[15] = 1;
    bus.video.reg[19] = 3;
    bus.video.reg[23] = 0x80;
    command(bus, 0, 0x21);
    bus.write16(0xc00000, 0x1234);
    require(bus.video.vram[0] == 0x1212 && bus.video.vram[1] == 0x1212 &&
            bus.video.reg[19] == 3 && bus.video.vram[32768] == 0xa5a5,
            "native fill rounding, length and bank preservation");

    bus.video.reg[0] = 16;
    bus.video.reg[1] = 32;
    bus.video.reg[10] = 1;
    bus.begin_line(0);
    require(bus.interrupt_level() == 6, "vertical request");
    bus.begin_line(37);
    bus.begin_line(38);
    require(bus.interrupt_level() == 0, "vertical request expiry");
    bus.begin_line(39);
    require(bus.interrupt_level() == 4, "horizontal reload interval");
    bus.begin_line(40);
    require(bus.interrupt_level() == 0, "horizontal request expiry");
}

void test_machine()
{
    Machine machine(cartridge());
    machine.frame();
    machine.frame();
    require(machine.frames == 2 && machine.cpu.stopped && machine.cpu.address[7] == 0xfffe00,
            "frame scheduler and supervisor stack after RTE");
    require(machine.cpu.data[1] == 4 && Word(machine.cpu.data[0]) == 65535,
            "MOVEQ, ADDQ and DBRA result");
    require(machine.bus.read32(0xff0000) == 0x12345678 && machine.bus.read16(0xff0020) == 2,
            "cartridge writes and interrupt handler");
    require(std::all_of(machine.video().begin(), machine.video().end(),
                        [](Pixel pixel) { return pixel == 0xee0000; }),
            "frame produced from guest register and palette writes");
}

void test_sound_bus()
{
    Machine machine(cartridge());
    constexpr std::array<Byte, 6> program{0x3e, 0x5a, 0x32, 0x00, 0x01, 0x76};
    auto &bus = machine.bus;
    bus.write16(0xa11100, 0x0100);
    for (unsigned i = 0; i < program.size(); ++i)
        bus.write8(0xa00000 + i, program[i]);
    machine.frame();
    require(bus.z80_read(0x100) == 0, "Z80 held in reset");
    bus.write16(0xa11200, 0x0100);
    machine.frame();
    require(bus.z80_read(0x100) == 0, "68000 retains the Z80 bus");
    bus.write16(0xa11100, 0);
    machine.frame();
    require(bus.z80_read(0x100) == 0x5a && bus.z80_read(0x2100) == 0x5a,
            "Z80 releases reset, executes and writes to mirrored RAM");

    bus.z80_write(0x4000, 0x24);
    bus.z80_write(0x4001, 0xff);
    bus.z80_write(0x4000, 0x25);
    bus.z80_write(0x4001, 3);
    bus.z80_write(0x4000, 0x27);
    bus.z80_write(0x4001, 5);
    require(bus.z80_read(0x4000) == 0x80, "FM busy flag starts on data write");
    bus.advance(144);
    require(bus.z80_read(0x4000) == 0x81, "FM timer A deadline");
    bus.advance(48);
    require(bus.z80_read(0x4000) == 1, "FM busy flag expires");
    bus.z80_write(0x4001, 0x10);
    require(bus.z80_read(0x4000) == 0x80, "FM timer A reset");
}

void test_synthesis()
{
    Ym2612 ym;
    ym.write(0, 0x3c, 1);
    ym.write(0, 0x5c, 31);
    ym.write(0, 0x8c, 15);
    ym.write(0, 0xa4, 0x24);
    ym.write(0, 0xa0, 0x3b);
    ym.write(0, 0xb4, 0x80);
    ym.write(0, 0x28, 0x80);
    unsigned crossings = 0;
    int previous = 0;
    int peak = 0;
    for (unsigned i = 0; i < 4200; ++i) {
        const auto [left, right] = ym.sample();
        require(!right, "FM left pan");
        peak = std::max(peak, left);
        crossings += left > 0 && previous <= 0;
        previous = left;
    }
    require(peak > 3000 && crossings >= 34 && crossings <= 36, "FM note at A4");
    ym.write(0, 0x28, 0);
    for (unsigned i = 0; i < 1024; ++i)
        ym.sample();
    require(ym.sample() == std::array{0, 0}, "FM key-off release");

    ym.write(1, 0xb6, 0x40);
    ym.write(0, 0x2a, 224);
    ym.write(0, 0x2b, 0x80);
    require(ym.sample() == std::array{0, 3072}, "DAC replaces channel six on the right");
    require(ym.sample(0, 50) == std::array{0, 1536}, "PCM level is independent of FM mute");
    require(ym.sample(100, 0) == std::array{0, 0}, "PCM mute");
    ym.write(0, 0x2b, 0);
    require(ym.sample() == std::array{0, 0}, "DAC disable");

    Machine machine(cartridge());
    machine.bus.write16(0xc00010, 0x0080);
    machine.bus.z80_write(0x7f11, 0x10);
    machine.bus.z80_write(0x7f11, 0x90);
    machine.frame();
    const auto audio = machine.audio();
    require(audio.size() / 2 >= 888 && audio.size() / 2 <= 890, "native stereo samples per video frame");
    const auto [quietest, loudest] = std::minmax_element(audio.begin(), audio.end());
    require(*quietest < -500 && *loudest > 500, "PSG tone through both CPU buses");
    for (unsigned i = 0; i < audio.size(); i += 2)
        require(audio[i] == audio[i + 1], "PSG sent to both stereo outputs");
    machine.bus.set_audio_levels({100, 100, 0});
    machine.frame();
    const auto muted = machine.audio();
    require(std::all_of(muted.begin(), muted.end(), [](auto value) { return value == 0; }),
            "PSG mute applies at the next frame");
}

void test_fm_modulation()
{
    Ym2612 ym;
    // Algorithm 4 routes operator 1 into operator 2. Leave operators 3 and 4 off.
    ym.write(0, 0xb0, 4);
    ym.write(0, 0xb4, 0x80);
    ym.write(0, 0x30, 1);
    ym.write(0, 0x38, 1);
    ym.write(0, 0x40, 27);
    ym.write(0, 0x50, 31);
    ym.write(0, 0x58, 31);
    ym.write(0, 0xa4, 0x24);
    ym.write(0, 0xa0, 0x3b);
    ym.write(0, 0x28, 0x30);

    constexpr double harmonic_phase = 2 * 6.283185307179586 * (1083 * 8.0 / (1 << 20));
    constexpr unsigned samples = 4096;
    double real = 0, imaginary = 0;
    for (unsigned i = 0; i < samples; ++i) {
        const int sample = ym.sample()[0];
        real += sample * std::cos(harmonic_phase * i);
        imaginary += sample * std::sin(harmonic_phase * i);
    }
    const double amplitude = std::hypot(real, imaginary) * 2 / samples;
    require(amplitude > 1800 && amplitude < 3600, "FM carrier second harmonic from operator phase modulation");
    for (unsigned i = 0; i < 128; ++i)
        require(ym.sample(0, 100) == std::array{0, 0}, "FM mute with PCM enabled");
}

void test_video_options()
{
    Renderer renderer;
    Video video;
    video.reg[1] = 0x40;
    video.reg[2] = 0x20;
    video.reg[4] = 1;
    video.reg[5] = 0x60;
    video.reg[12] = 0x81;
    video.set_color(1, 0x000e);
    video.set_color(2, 0x00e0);
    std::fill_n(video.vram.begin() + 16, 16, 0x1111);
    std::fill_n(video.vram.begin() + 32, 16, 0x2222);
    video.vram[4096 + 31] = video.vram[4096 + 8] = 2;
    video.vram[4096] = 1;

    std::array<Pixel, screen_width> normal;
    std::array<Pixel, wide_width> wide;
    renderer.render(video, 0, false, normal);
    renderer.render(video, 0, false, wide);
    require(std::equal(normal.begin(), normal.end(), wide.begin() + wide_border), "widescreen preserves the central pixels");
    require(wide[wide_border - 1] == 0x00ee00 && wide[wide_border + screen_width] == 0x00ee00,
            "widescreen samples tiles beyond both edges");

    const unsigned table = 0x6000;
    for (unsigned index = 0; index < 30; ++index) {
        video.vram[table + 4 * index] = 128;
        video.vram[table + 4 * index + 1] = index == 29 ? 0 : index + 1;
        video.vram[table + 4 * index + 2] = 1;
        video.vram[table + 4 * index + 3] = 128 + 10 * index;
    }
    renderer.render(video, 0, false, normal);
    require(normal[29 * 10] != 0xee0000, "native line drops sprites past its quota");
    renderer.render(video, 0, false, wide);
    require(wide[wide_border + 29 * 10] == normal[29 * 10], "widescreen alone retains the sprite quota");
    renderer.render(video, 0, false, normal, true);
    require(normal[29 * 10] == 0xee0000, "Mark VI draws the whole native list");

    std::vector<SpritePiece> objects(180, {32, 128, 0, 2, 64, 64});
    objects.front().descriptor = 1;
    objects.back().x = 280;
    renderer.render(video, 0, false, normal, true, {true, objects});
    require(normal[32] == 0xee0000 && normal[280] == 0x00ee00,
            "Mark VI keeps priority and draws pieces beyond the hardware table size");
    renderer.render(video, 0, false, wide, true, {true, objects});
    require(std::equal(normal.begin(), normal.end(), wide.begin() + wide_border),
            "Mark VI uses the same list with either aspect ratio");
}

void test_scene_publication()
{
    Cartridge rom{};
    write_words(rom, 0x108, {0, 0x0100, 0, 0x0150});
    Bus bus(rom);
    SceneSprites scene;
    const unsigned object = 0xff2000;
    const unsigned head = 0xff4800;
    const unsigned table = 0xf000;
    bus.video.reg[5] = table / 512;
    bus.write32(0xff40b8, object);
    bus.write32(0xff1210, head);
    bus.write32(object + 0x10, 0x1dd4e0);
    bus.write32(object + 0x1c, 0x100);
    bus.write8(object + 0x20, 0xff);
    bus.write8(object + 0x2b, 4);
    scene.instruction(bus, 1, 0x1dd588, 0, object, 0, 0);
    scene.instruction(bus, 1, 0x170344, 0, 0, 0, 0);
    scene.upload(bus, 1, head, table, 320, 2);
    require(!scene.displayed(table).active, "unfinished constructor is not displayed");
    scene.instruction(bus, 1, 0x170836, 0, 0, 0, 0);
    scene.upload(bus, 1, head, table, 320, 2);
    require(scene.displayed(table).active && scene.displayed(table).pieces.size() == 1,
            "Mark VI publishes the verified blink pose at the matching SAT upload");
    scene.vram_write(table);
    require(!scene.displayed(table).active, "external sprite-table write invalidates the host list");
}

void test_interpolation()
{
    Video video;
    video.reg[1] = 0x40;
    video.reg[5] = 0x60;
    video.reg[12] = 0x81;
    video.set_color(1, 0x000e);
    std::fill_n(video.vram.begin() + 16, 16, 0x1111);
    const unsigned sat = 0x6000;
    video.vram[sat] = 128;
    video.vram[sat + 2] = 1;
    video.vram[sat + 3] = 148;
    FrameInterpolation interpolation;
    interpolation.begin(video, {}, screen_width, false);
    require(!interpolation.between_native(), "first presentation starts with the current sprites");
    video.vram[sat + 3] = 160;
    interpolation.begin(video, {}, screen_width, false);
    Renderer renderer;
    std::array<Pixel, screen_width> native_row{}, row{};
    renderer.render(video, 0, false, native_row, false, {}, {row, {}, interpolation.between_native()});
    require(native_row[26] == 0 && native_row[32] == 0xee0000 && renderer.captured_sprite(26) == 0 &&
            renderer.captured_sprite(32) != 0, "the paired render leaves the native frame and sprite data intact");
    require(row[25] == 0 && row[26] == 0xee0000 && row[33] == 0xee0000 && row[34] == 0,
            "120 Hz draws the native sprite at its midpoint");
    video.vram[sat + 3] = 300;
    interpolation.begin(video, {}, screen_width, false);
    require(!interpolation.between_native(), "discontinuous SAT positions are not interpolated");

    std::array<SpritePiece, 2> before{{{10, 128, 0, 1, 64, 64, 1}, {20, 128, 0, 1, 64, 64, 2}}};
    std::array<SpritePiece, 2> after{{{28, 128, 0, 1, 64, 64, 2}, {60, 128, 0, 1, 64, 64, 3}}};
    interpolation.begin(video, {true, before, 1}, wide_width, true);
    interpolation.begin(video, {true, after, 2}, wide_width, true);
    const auto mid = interpolation.between_objects({true, after, 2});
    require(mid.active && mid.pieces.size() == 2 && mid.pieces[0].x == 24 && mid.pieces[1].x == 60,
            "Mark VI matches identity across reordering and keeps the current visible pieces");
    require(!interpolation.between_objects({true, after, 3}).active,
            "an in-frame upload invalidates the cached midpoint");
    interpolation.begin(video, {true, after, 2}, screen_width, true);
    require(!interpolation.between_objects({true, after, 2}).active, "aspect changes clear sprite motion");
}

} // namespace

int main()
{
    test_bus();
    test_machine();
    test_sound_bus();
    test_synthesis();
    test_fm_modulation();
    test_video_options();
    test_scene_publication();
    test_interpolation();
    std::cout << "Mark V 68000, Z80, bus, video, interrupts and audio self-tests passed\n";
}
