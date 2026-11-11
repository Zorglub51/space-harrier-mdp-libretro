#include "machine.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>

int main(int argc, char **argv)
{
    using namespace markv;
    if (argc != 2) {
        std::cerr << "usage: sh1-attract SPACE_HARRIER.smp\n";
        return 2;
    }
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) {
        std::cerr << "could not open the Space Harrier ROM\n";
        return 2;
    }
    const std::vector<Byte> cartridge((std::istreambuf_iterator<char>(input)), {});
    if (cartridge.size() != 0x3e0000) {
        std::cerr << "the regression requires the original Space Harrier Mark V ROM\n";
        return 2;
    }
    Machine machine(cartridge);
    if (!machine.bus.is_object_average(0x17264a)) {
        std::cerr << "the regression requires the original Space Harrier Mark V ROM\n";
        return 2;
    }

    constexpr unsigned crash_frame = 9011;
    constexpr unsigned frames = 54000;
    Frame previous{};
    unsigned changes = 0;
    for (unsigned i = 1; i <= frames; ++i) {
        machine.frame();
        if (machine.cpu.pc == 0x1ea860) {
            std::cerr << "Space Harrier reached its divide-by-zero screen at frame " << i << '\n';
            return 1;
        }
        const auto video = machine.video();
        if (i > crash_frame && i % 300 == 0 && !std::equal(video.begin(), video.end(), previous.begin())) {
            ++changes;
            std::copy(video.begin(), video.end(), previous.begin());
        }
    }
    if (changes < 30) {
        std::cerr << "attract mode stopped advancing after the stage 15 demo\n";
        return 1;
    }
    std::cout << "Space Harrier attract mode passed " << frames << " frames and "
              << changes << " changing video checkpoints after the old crash\n";
}
