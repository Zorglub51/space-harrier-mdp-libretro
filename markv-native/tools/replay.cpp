#include "video.hpp"

#include <algorithm>
#include <bit>
#include <charconv>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

using namespace markv;
using Clock = std::chrono::steady_clock;
constexpr unsigned words_per_line = 578;
constexpr unsigned page_words = 256;
constexpr unsigned logical_pages = 256;
static_assert(std::endian::native == std::endian::little);

using Frame = std::array<Pixel, screen_width * screen_height>;
using Line = std::array<Word, words_per_line>;

struct Capture {
    std::filesystem::path file;
    std::array<Line, screen_height> lines;
    std::vector<Word> pages;
    std::vector<Word> maps;
    Frame reference;
};

template<class Array>
void read(std::ifstream &stream, Array &values)
{
    const auto bytes = values.size() * sizeof(values[0]);
    if (!stream.read(reinterpret_cast<char *>(values.data()), bytes))
        throw std::runtime_error("incomplete capture");
}

Capture load(const std::filesystem::path &file)
{
    try {
        std::ifstream stream(file, std::ios::binary);
        std::array<char, 4> magic{};
        read(stream, magic);
        if (magic != std::array{'S', 'H', 'G', 'P'})
            throw std::runtime_error("invalid SHGP signature");

        std::array<std::uint32_t, 2> counts{};
        read(stream, counts);
        const auto [pages, epochs] = counts;
        if (pages < logical_pages || pages > 65536 || epochs == 0 || epochs > screen_height)
            throw std::runtime_error("invalid SHGP dimensions");

        Capture capture;
        capture.file = file;
        read(stream, capture.lines);
        capture.pages.resize(pages * page_words);
        capture.maps.resize(epochs * logical_pages);
        read(stream, capture.pages);
        read(stream, capture.maps);
        read(stream, capture.reference);
        if (stream.peek() != std::char_traits<char>::eof())
            throw std::runtime_error("unexpected data after reference frame");
        for (const auto &line : capture.lines)
            if (line[576] >= epochs || (line[577] & ~1u))
                throw std::runtime_error("unsupported scanline flags or VRAM epoch");
        for (Word page : capture.maps)
            if (page >= pages)
                throw std::runtime_error("VRAM page outside the capture");
        return capture;
    } catch (const std::exception &error) {
        throw std::runtime_error(file.string() + ": " + error.what());
    }
}

void compare(const Capture &capture, unsigned y, const Renderer &renderer,
             std::span<const Pixel, screen_width> line)
{
    for (unsigned x = 0; x < screen_width; ++x) {
        const Pixel expected = capture.reference[y * screen_width + x] & 0xffffff;
        if (line[x] != expected || renderer.captured_sprite(x) != capture.lines[y][256 + x]) {
            std::cerr << capture.file << " (" << x << ',' << y << ") RGB "
                      << std::hex << line[x] << '/' << expected << " sprites "
                      << renderer.captured_sprite(x) << '/' << capture.lines[y][256 + x]
                      << std::dec << '\n';
            throw std::runtime_error("reference mismatch");
        }
    }
}

template<bool Compare>
Clock::duration replay(const Capture &capture, Video &video, Renderer &renderer, Frame &frame)
{
    unsigned active_epoch = screen_height;
    const Word *active_pages = nullptr;
    Clock::duration raster{};
    for (unsigned y = 0; y < screen_height; ++y) {
        const Line &line = capture.lines[y];
        const unsigned epoch = line[576];
        if (epoch != active_epoch) {
            const Word *pages = capture.maps.data() + epoch * logical_pages;
            for (unsigned page = 0; page < logical_pages; ++page)
                if (!active_pages || pages[page] != active_pages[page])
                    std::memcpy(video.vram.data() + page * page_words,
                                capture.pages.data() + pages[page] * page_words,
                                page_words * sizeof(Word));
            active_epoch = epoch;
            active_pages = pages;
        }
        for (unsigned index = 0; index < video.reg.size(); ++index)
            video.reg[index] = Byte(line[index]);
        std::copy_n(line.data() + 64, video.vscroll.size(), video.vscroll.begin());
        for (unsigned index = 0; index < video.cram.size(); ++index)
            if (line[128 + index] != video.cram[index])
                video.set_color(index, line[128 + index]);

        std::span<Pixel, screen_width> pixels(frame.data() + y * screen_width, screen_width);
        if constexpr (Compare) {
            renderer.render(video, y, line[577] & 1, pixels);
            compare(capture, y, renderer, pixels);
        } else {
            const auto before = Clock::now();
            renderer.render(video, y, line[577] & 1, pixels);
            raster += Clock::now() - before;
        }
    }
    return raster;
}

double milliseconds(Clock::duration time)
{
    return std::chrono::duration<double, std::milli>(time).count();
}

void report(std::string_view name, std::vector<double> &samples)
{
    std::sort(samples.begin(), samples.end());
    const auto quantile = [&](unsigned percent) {
        return samples[(samples.size() * percent + 99) / 100 - 1];
    };
    std::cout << name << " frames=" << samples.size() << std::fixed << std::setprecision(3)
              << " median_ms=" << quantile(50) << " p95_ms=" << quantile(95)
              << " p99_ms=" << quantile(99) << " max_ms=" << samples.back() << '\n';
}

} // namespace

int main(int argc, char **argv)
{
    try {
        const std::string_view mode = argc > 1 ? argv[1] : "";
        const bool bench = mode == "--bench";
        const int first = bench ? 3 : 2;
        if (argc <= first || (mode != "--verify" && !bench))
            throw std::runtime_error("usage: markv-replay --verify CAPTURE... | --bench REPEATS CAPTURE...");
        unsigned repeats = 0;
        if (bench) {
            const std::string_view text(argv[2]);
            const auto parsed = std::from_chars(text.begin(), text.end(), repeats);
            if (parsed.ec != std::errc{} || parsed.ptr != text.end() || !repeats || repeats > 1000)
                throw std::runtime_error("invalid repeat count");
        }

        Video video;
        Renderer renderer;
        Frame frame;
        std::vector<Capture> captures;
        if (bench)
            captures.reserve(argc - first);
        for (int i = first; i < argc; ++i) {
            auto capture = load(argv[i]);
            replay<true>(capture, video, renderer, frame);
            if (bench)
                captures.push_back(std::move(capture));
        }
        const unsigned verified = argc - first;
        std::cout << "Verified " << verified << " frames, "
                  << std::uint64_t(verified) * screen_width * screen_height
                  << " exact RGB pixels and sprite samples\n";
        if (!bench)
            return 0;

        std::vector<double> raster, total;
        raster.reserve(repeats * captures.size());
        total.reserve(raster.capacity());
        std::uint32_t checksum = 0;
        for (unsigned pass = 0; pass < repeats; ++pass) {
            for (const auto &capture : captures) {
                const auto start = Clock::now();
                const auto raster_time = replay<false>(capture, video, renderer, frame);
                total.push_back(milliseconds(Clock::now() - start));
                raster.push_back(milliseconds(raster_time));
                checksum = checksum * 31 + frame[raster.size() % frame.size()];
            }
        }
        report("Raster", raster);
        report("Replay with VRAM reconstruction", total);
        std::cout << "checksum=" << std::hex << checksum << std::dec << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
