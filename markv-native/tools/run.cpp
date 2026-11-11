#include "machine.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string_view>
#include <vector>

int main(int argc, char **argv)
{
    using namespace markv;
    bool exercise = false, widescreen = false, mark_vi = false;
    while (argc > 1) {
        const std::string_view option(argv[1]);
        if (option == "--exercise")
            exercise = true;
        else if (option == "--widescreen")
            widescreen = true;
        else if (option == "--mark-vi")
            mark_vi = true;
        else
            break;
        --argc;
        ++argv;
    }
    if (argc < 3 || argc > 4) {
        std::cerr << "usage: markv-run [--exercise] [--widescreen] [--mark-vi] ROM FRAMES [OUTPUT.ppm]\n";
        return 2;
    }
    try {
        unsigned frames = 0;
        const std::string_view count(argv[2]);
        const auto parsed = std::from_chars(count.begin(), count.end(), frames);
        if (parsed.ec != std::errc{} || parsed.ptr != count.end() || !frames)
            throw std::runtime_error("invalid frame count");
        std::ifstream input(argv[1], std::ios::binary | std::ios::ate);
        const auto length = input.tellg();
        if (length < 8 || length > 0x400000)
            throw std::runtime_error("could not load ROM in the Mark V cartridge window");
        input.seekg(0);
        std::vector<Byte> rom(static_cast<unsigned>(length));
        if (!input.read(reinterpret_cast<char *>(rom.data()), length))
            throw std::runtime_error("could not read complete ROM");
        Machine machine(rom);
        machine.bus.set_video_options(widescreen, mark_vi);
        if ((widescreen || mark_vi) && !machine.bus.supports_video_options())
            throw std::runtime_error("enhanced rendering requires a supported Mark V ROM");
        std::vector<double> times;
        times.reserve(frames);
        std::uint64_t audio_frames = 0;
        int audio_peak = 0;
        std::size_t sprite_peak = 0;
        using Clock = std::chrono::steady_clock;
        try {
            for (unsigned i = 0; i < frames; ++i) {
                if (exercise) {
                    Byte pad = 0xff;
                    for (const unsigned start : {700u, 1300u, 1900u, 2500u})
                        if (i >= start && i < start + 8)
                            pad &= ~0x80;
                    if (i >= 2600) {
                        if (i % 4 < 2)
                            pad &= ~0x10;
                        pad &= ~(1 << ((i / 90) & 3));
                    }
                    machine.bus.buttons(pad);
                }
                const auto start = Clock::now();
                machine.frame();
                times.push_back(std::chrono::duration<double, std::milli>(Clock::now() - start).count());
                if (mark_vi)
                    sprite_peak = std::max(sprite_peak, machine.bus.scene().pieces.size());
                const auto audio = machine.audio();
                audio_frames += audio.size() / 2;
                const auto [minimum, maximum] = std::minmax_element(audio.begin(), audio.end());
                if (!audio.empty())
                    audio_peak = std::max({audio_peak, -*minimum, int(*maximum)});
            }
        } catch (const Z80Fault &fault) {
            std::cerr << "unsupported Z80 instruction at pc=0x" << std::hex << fault.pc
                      << " opcode=0x" << unsigned(fault.opcode) << std::dec
                      << " frame=" << machine.frames << " slice=" << machine.line() << '\n';
            return 1;
        } catch (const CpuFault &fault) {
            const char *reason = fault.reason == CpuFault::Reason::address ? "unaligned address" :
                                 fault.reason == CpuFault::Reason::privilege ? "privilege violation" :
                                 "unsupported instruction";
            std::cerr << reason << " at pc=0x" << std::hex << fault.pc << " opcode=0x" << fault.opcode
                      << " address=0x" << fault.address << std::dec
                      << " frame=" << machine.frames << " slice=" << machine.line()
                      << " instructions=" << machine.executed << '\n';
            return 1;
        }
        std::sort(times.begin(), times.end());
        const auto percentile = [&times](std::size_t percent) {
            return times[(times.size() * percent - 1) / 100];
        };
        const double mean = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
        std::cout << "Frames " << machine.frames << " instructions " << machine.executed
                  << std::fixed << std::setprecision(3)
                  << " mean_ms=" << mean << " median_ms=" << percentile(50)
                  << " p95_ms=" << percentile(95) << " p99_ms=" << percentile(99)
                  << " max_ms=" << times.back() << " audio_frames=" << audio_frames
                  << " audio_peak=" << audio_peak;
        if (mark_vi)
            std::cout << " mark_vi_sprite_peak=" << sprite_peak;
        std::cout << " pc=0x" << std::hex << machine.cpu.pc << '\n';
        if (argc == 4) {
            std::ofstream image(argv[3], std::ios::binary);
            image << "P6\n" << machine.video_width() << ' ' << screen_height << "\n255\n";
            for (const Pixel pixel : machine.video()) {
                const char rgb[] = {char(pixel >> 16), char(pixel >> 8), char(pixel)};
                image.write(rgb, sizeof(rgb));
            }
            if (!image)
                throw std::runtime_error("failed to write PPM");
        }
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
