"""Keep Harrier moving through native pose changes without moving his pieces apart."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PlayerInterpolation(unittest.TestCase):
    def test_native_pose_changes_and_lifecycle_cuts(self):
        source = r'''
#include "sh1_markvi.h"
#include <cassert>
#include <unordered_map>

using u16 = std::uint16_t;
using u32 = std::uint32_t;
using sh1_markvi::sprite;
constexpr u32 player = 0xff21ac;

struct Memory {
    std::unordered_map<u32, u16> words;
    u16 read(u32 address) const {
        const auto i = words.find(address);
        return i == words.end() ? 0 : i->second;
    }
    void put(u32 address, u16 value) { words[address] = value; }
    void lng(u32 address, u32 value) {
        put(address, value >> 16); put(address + 2, value);
    }
};

struct Fixture {
    Memory old_memory, new_memory;
    std::vector<sprite> old_sprites, new_sprites;

    Fixture() {
        for (auto *m : {&old_memory, &new_memory}) {
            m->lng(0xff16c8, player);
            m->lng(player + 0x10, 0x1ddf52);
            m->put(player + 0x0a, 0); // Native, unscaled Harrier.
            m->put(player + 0x20, 0); // Pose zero; the drawing table changes.
            m->put(player + 0x2a, 4); // No shadow in the native body fixture.
        }
        old_memory.lng(player + 0x1c, 0x620);
        new_memory.lng(player + 0x1c, 0x636);
        old_memory.put(player + 0x0c, 128); old_memory.put(player + 0x0e, 144);
        new_memory.put(player + 0x0c, 160); new_memory.put(player + 0x0e, 160);
        new_memory.put(player + 0x28, 0x0100); // Horizontal flip changes natively.

        // The native 0620/0636 four-piece layouts, with the current pose flipped.
        // These are different local coordinates, not a morph of the old drawing.
        old_sprites = {
            {208, 0x0f00, 0x2020, 236, 0x1000, player, 0x1ddf52, 0x620, 0},
            {208, 0x0300, 0x2030, 268, 0x1000, player, 0x1ddf52, 0x620, 1},
            {240, 0x0f00, 0x2034, 236, 0x1000, player, 0x1ddf52, 0x620, 2},
            {240, 0x0300, 0x2044, 268, 0x1000, player, 0x1ddf52, 0x620, 3},
        };
        new_sprites = {
            {224, 0x0f00, 0xa860, 276, 0x1000, player, 0x1ddf52, 0x636, 0},
            {224, 0x0300, 0xa870, 268, 0x1000, player, 0x1ddf52, 0x636, 1},
            {256, 0x0f00, 0xa874, 276, 0x1000, player, 0x1ddf52, 0x636, 2},
            {256, 0x0300, 0xa884, 268, 0x1000, player, 0x1ddf52, 0x636, 3},
        };
    }

    std::vector<sprite> sample(unsigned numerator = 1, unsigned denominator = 4,
                              const sh1_player_motion::history *latest = nullptr,
                              unsigned phase = 0) {
        auto before = [this](u32 a) { return old_memory.read(a); };
        auto now = [this](u32 a) { return new_memory.read(a); };
        return sh1_markvi::interpolate_player(old_sprites, new_sprites,
                                              before, now, numerator, denominator, latest, phase);
    }
};

static void same_artwork(const sprite &actual, const sprite &current) {
    assert(actual.size == current.size && actual.attr == current.attr);
    assert(actual.zoom == current.zoom && actual.owner == current.owner);
    assert(actual.routine == current.routine && actual.descriptor == current.descriptor);
    assert(actual.part == current.part);
}

static std::int64_t x_times(const sprite &s, unsigned denominator) {
    return s.position_divisor ? s.precise_x * denominator / s.position_divisor
                              : std::int64_t(s.x) * denominator;
}

static std::int64_t y_times(const sprite &s, unsigned denominator) {
    return s.position_divisor ? s.precise_y * denominator / s.position_divisor
                              : std::int64_t(s.y) * denominator;
}

static void native_body(const std::vector<sprite> &actual, const Fixture &f) {
    assert(actual.size() == f.new_sprites.size());
    for (unsigned i = 0; i < actual.size(); ++i) {
        assert(actual[i].x == f.new_sprites[i].x && actual[i].y == f.new_sprites[i].y);
        assert(actual[i].position_divisor == 0);
        same_artwork(actual[i], f.new_sprites[i]);
    }
}

int main() {
    Fixture f;
    // Old matching rejects this real direction/pose change and jumps immediately.
    auto old_result = sh2_markvi::interpolate(f.old_sprites, f.new_sprites, 1, 4);
    assert(old_result[0].x == 276);
    // The displayed anchor advances 136,144,152,160 and 148,152,156,160.
    // Every piece retains exactly the current native drawing's local offsets.
    for (unsigned step = 1; step <= 4; ++step) {
        const auto result = f.sample(step, 4);
        assert(result.size() == 4);
        for (unsigned i = 0; i < result.size(); ++i) {
            assert(x_times(result[i], 4) == (f.new_sprites[i].x - (4 - step) * 8) * 4);
            assert(y_times(result[i], 4) == (f.new_sprites[i].y - (4 - step) * 4) * 4);
            assert(result[i].x == f.new_sprites[i].x && result[i].y == f.new_sprites[i].y);
            same_artwork(result[i], f.new_sprites[i]);
        }
        assert(x_times(result[1], 4) - x_times(result[0], 4) == -32);
        assert(y_times(result[2], 4) - y_times(result[0], 4) == 128);
    }
    native_body(f.sample(4, 4), f);
    native_body(f.sample(5, 4), f);
    native_body(f.sample(1, 0), f);

    // Rendering must follow completed game-loop coordinates even if the
    // emitter/SAT snapshot has not yet published them. Keep CURRENT art and
    // fractional positions; an emitter endpoint must not disable this clock.
    sh1_player_motion::history latest;
    latest.sample(player, 100, 168, 164);
    latest.sample(player, 100, 169, 165); // Incomplete next update is ignored.
    latest.sample(player, 101, 169, 165);
    assert(latest.span == 2);
    for (unsigned age = 0; age <= 3; ++age) {
        latest.age = age;
        for (unsigned phase = 0; phase < 2; ++phase) {
            const unsigned step = std::min(4U, std::min(age, 2U) * 2 + phase + 1);
            for (unsigned emitter_step : {1U, 4U, 5U}) {
                const auto result = f.sample(emitter_step, 4, &latest, phase);
                for (unsigned i = 0; i < result.size(); ++i) {
                    assert(result[i].position_divisor == 4);
                    assert(result[i].precise_x == std::int64_t(f.new_sprites[i].x + 8) * 4 + step);
                    assert(result[i].precise_y == std::int64_t(f.new_sprites[i].y + 4) * 4 + step);
                    same_artwork(result[i], f.new_sprites[i]);
                    assert(result[i].x == f.new_sprites[i].x && result[i].y == f.new_sprites[i].y);
                }
            }
        }
    }
    // Invalid, recycled and discontinuous histories retain the .23 path.
    for (unsigned cut = 0; cut < 7; ++cut) {
        auto bad = latest;
        switch (cut) {
        case 0: bad.valid = false; break;
        case 1: bad.owner += 0x54; break;
        case 2: bad.span = 0; break;
        case 3: bad.span = sh1_player_motion::max_interval + 1; break;
        case 4: bad.x[0] = bad.x[1] + 129; break;
        case 5: bad.y[1] += 129; break;
        case 6: bad.x[0] = bad.x[1] = 400; break;
        }
        native_body(f.sample(4, 4, &bad), f);
    }

    // Live sampling is read-only, uses the completed native counter and cuts
    // on pause/death/invulnerability/blink/unknown art rather than resurrecting
    // a stale body. Memory changes are controlled independently from the SAT.
    auto live_read = [&f](u32 a) { return f.new_memory.read(a); };
    f.new_memory.lng(0xff3d08, 100);
    sh1_markvi::sample_player(live_read);
    assert(sh1_player_motion::state.valid && sh1_player_motion::state.x[1] == 160);
    f.new_memory.put(player + 0x0c, 168);
    sh1_markvi::sample_player(live_read);
    assert(sh1_player_motion::state.x[1] == 160);
    f.new_memory.lng(0xff3d08, 101);
    sh1_markvi::sample_player(live_read);
    assert(sh1_player_motion::state.x[1] == 168 && sh1_player_motion::state.span == 2);
    for (unsigned cut = 0; cut < 9; ++cut) {
        Fixture live;
        switch (cut) {
        case 0: live.new_memory.put(0xff3d0e, 1); break;
        case 1: live.new_memory.lng(player + 0x10, 0x1dd698); break;
        case 2: live.new_memory.lng(player + 0x10, 0x1dd4e0); break;
        case 3: live.new_memory.put(player + 0x2a, 0x84); break;
        case 4: live.new_memory.put(player + 0x0a, 1); break;
        case 5: live.new_memory.put(player + 0x20, 0x0100); break;
        case 6: live.new_memory.lng(player + 0x1c, 0x621); break;
        case 7: live.new_memory.lng(0xff16c8, player | 1); break;
        case 8: live.new_memory.lng(0xff16c8, 0xfffffe); break;
        }
        sh1_markvi::sample_player([&live](u32 a) { return live.new_memory.read(a); });
        assert(!sh1_player_motion::state.valid);
        sh1_markvi::sample_player(live_read);
        assert(sh1_player_motion::state.valid && sh1_player_motion::state.span == 1);
    }
    f.new_memory.put(player + 0x0c, 160);

    // Three native pixels over four subframes retain exact 3/4-pixel steps.
    // No early integer or fixed-point rounding is allowed in either direction.
    for (bool backwards : {false, true}) {
        Fixture fractional;
        const int target_x = backwards ? 125 : 131;
        const int target_y = backwards ? 141 : 147;
        fractional.new_memory.put(player + 0x0c, target_x);
        fractional.new_memory.put(player + 0x0e, target_y);
        for (auto &s : fractional.new_sprites) {
            s.x = u16(int(s.x) + target_x - 160);
            s.y = u16(int(s.y) + target_y - 160);
        }
        for (unsigned step = 1; step < 4; ++step) {
            const auto result = fractional.sample(step, 4);
            for (unsigned i = 0; i < result.size(); ++i) {
                const auto &s = result[i];
                assert(s.position_divisor == 4);
                const int remainder = (backwards ? 3 : -3) * (4 - step);
                assert(s.precise_x == std::int64_t(fractional.new_sprites[i].x) * 4 + remainder);
                assert(s.precise_y == std::int64_t(fractional.new_sprites[i].y) * 4 + remainder);
                assert(s.x == fractional.new_sprites[i].x && s.y == fractional.new_sprites[i].y);
                same_artwork(s, fractional.new_sprites[i]);
            }
        }
        native_body(fractional.sample(4, 4), fractional);
    }

    // A measured interval can also yield thirds/sixths, which a finite binary
    // fixed-point format cannot represent exactly. Keep the rational values.
    for (unsigned denominator : {3, 6}) {
        Fixture fractional;
        fractional.new_memory.put(player + 0x0c, 129);
        fractional.new_memory.put(player + 0x0e, 145);
        for (auto &s : fractional.new_sprites) { s.x -= 31; s.y -= 15; }
        for (unsigned step = 1; step < denominator; ++step) {
            const auto result = fractional.sample(step, denominator);
            for (unsigned i = 0; i < result.size(); ++i) {
                assert(result[i].position_divisor == denominator);
                assert(result[i].precise_x ==
                       std::int64_t(fractional.new_sprites[i].x) * denominator - (denominator - step));
                assert(result[i].precise_y ==
                       std::int64_t(fractional.new_sprites[i].y) * denominator - (denominator - step));
            }
        }
    }

    // A sprite that is absent now is never recreated, even if the player moves.
    Fixture missing_now;
    missing_now.new_sprites.clear();
    assert(missing_now.sample().empty());

    // An old shadow does not stand in for the missing visible player body.
    Fixture shadow_only;
    shadow_only.old_sprites.resize(1);
    shadow_only.old_sprites[0].part = 0x200;
    native_body(shadow_only.sample(), shadow_only);

    // Other actors and the ground shadow retain the shared interpolation rules.
    Fixture mixed;
    const sprite other_old{180, 0, 1, 100, 1024, 0xff5000, 0x1234, 0x800, 0};
    auto other_new = other_old; other_new.x = 132; other_new.y = 196; other_new.zoom = 2048;
    auto shadow_old = other_old; shadow_old.owner = player; shadow_old.routine = 0x1ddf52;
    shadow_old.part = 0x200;
    auto shadow_new = shadow_old; shadow_new.x = 164; shadow_new.y = 212;
    mixed.old_sprites.push_back(other_old); mixed.new_sprites.push_back(other_new);
    mixed.old_sprites.push_back(shadow_old); mixed.new_sprites.push_back(shadow_new);
    const auto mixed_result = mixed.sample(1, 2);
    assert(mixed_result[4].x == 116 && mixed_result[4].y == 188 && mixed_result[4].zoom == 1536);
    assert(mixed_result[5].x == 132 && mixed_result[5].y == 196);
    mixed.new_sprites[4].descriptor++;
    assert(mixed.sample(1, 2)[4].x == 132); // Nonplayer artwork changes still cut.

    // Each condition breaks continuity: death/respawn, native hiding, another
    // player generation, unknown artwork, scaling or a large position jump.
    for (unsigned cut = 0; cut < 18; ++cut) {
        Fixture c;
        switch (cut) {
        case 0: c.old_memory.lng(player + 0x10, 0x1dd698); break;
        case 1: c.new_memory.lng(player + 0x10, 0x1dd698); break;
        case 2: c.old_memory.put(player + 0x20, 0xff00); break;
        case 3: c.new_memory.put(player + 0x20, 0xfe00); break;
        case 4: c.old_memory.put(player + 0x2a, 0x84); break;
        case 5: c.new_memory.put(player + 0x2a, 0x84); break;
        case 6: c.old_memory.lng(0xff16c8, player + 0x54); break;
        case 7: c.new_memory.lng(0xff16c8, player + 0x54); break;
        case 8: c.old_memory.lng(player + 0x1c, 0x678); break;
        case 9: c.new_memory.lng(player + 0x1c, 0x712); break;
        case 10: c.old_memory.put(player + 0x0a, 1); break;
        case 11: c.new_memory.put(player + 0x0a, 1); break;
        case 12: c.old_sprites.clear(); break;
        case 13: c.new_memory.put(player + 0x0c, 258); break;
        case 14: c.new_memory.put(player + 0x0e, 274); break;
        case 15: c.old_memory.lng(0xff16c8, player | 1); break;
        case 16: c.new_memory.lng(0xff16c8, 0xfffffe); break;
        case 17: c.old_memory.lng(player + 0x1c, 0x621); break;
        }
        native_body(c.sample(), c);
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / 'player.cpp'
            source_path.write_text(source)
            binary = Path(directory) / 'player'
            subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
                '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT / 'src/markv'), str(source_path), '-o', str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
