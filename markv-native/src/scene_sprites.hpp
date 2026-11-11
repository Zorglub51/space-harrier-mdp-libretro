#pragma once

#include "video.hpp"

#include <bitset>
#include <vector>

namespace markv {

class Bus;

class SceneSprites {
public:
    void clear();
    void instruction(Bus &bus, unsigned game, unsigned pc, unsigned a0, unsigned a2, unsigned d4, Word status);
    void upload(Bus &bus, unsigned game, unsigned source, unsigned dest, unsigned words, unsigned stride);
    void vram_write(unsigned address);
    SpriteList displayed(unsigned table) const;

private:
    static constexpr unsigned sat_words = 80 * 4;

    struct List {
        std::vector<SpritePiece> pieces;
        std::array<Word, sat_words> signature{};
        unsigned source = 0;
        bool ready = false;
    };

    bool construct(Bus &bus, unsigned game, std::vector<SpritePiece> &out);

    std::array<List, 2> banks;
    List presented;
    std::vector<unsigned> objects;
    std::bitset<32768> visited, boss_thinning;
    unsigned building = 2, front_bank = 0, front_table = 0;
    std::uint64_t generation = 0;
    unsigned blinking_player = 0, blinking_handler = 0, visible_player_pose = 0;
};

} // namespace markv
