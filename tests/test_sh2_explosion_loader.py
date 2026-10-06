"""Exercise the optional donor loader and state-mode boundary without game data.

MAME file I/O, SHA-1 and the guest-code patch builder are stubbed, while the
production loader, transactional copy and state validation run unchanged.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

CORE_FILE = r'''
#pragma once
#include <cstdint>
#include <fstream>
#include <memory>
#include <string>
#include <system_error>
#include <utility>
#define OPEN_FLAG_READ 1
namespace util {
struct core_file {
    using ptr = std::unique_ptr<core_file>;
    std::ifstream stream;
    static std::error_condition open(const std::string &path, unsigned, ptr &file) {
        file.reset(new core_file);
        file->stream.open(path, std::ios::binary);
        return file->stream ? std::error_condition{} : std::make_error_condition(std::errc::no_such_file_or_directory);
    }
    std::error_condition length(std::uint64_t &size) {
        stream.seekg(0, std::ios::end); size = stream.tellg(); stream.seekg(0);
        return {};
    }
};
inline std::pair<std::error_condition, std::size_t> read(core_file &f, void *p, std::size_t n) {
    f.stream.read(static_cast<char *>(p), n);
    return {{}, static_cast<std::size_t>(f.stream.gcount())};
}
}
'''
HASH = r'''
#pragma once
#include <cstdint>
#include <string>
namespace util {
struct sha1_value { bool good; std::string as_string() const {
    return good ? "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72" : std::string(40, '0');
}};
struct sha1_creator { static sha1_value simple(const std::uint8_t *p, std::size_t n) {
    return {n == 0x3e0000 && p[0] == 0x5a};
}};
}
'''
PATCH = r'''
#pragma once
namespace markv {
inline bool reject_patch = false;
inline bool apply_sh2_enemy_explosions(std::uint8_t *p, std::size_t n, const std::uint8_t *, std::size_t) {
    p[0] = 0x11; p[n-1] = 0x22;
    return !reject_patch;
}
}
'''
PROBE = r'''
#include "sh2_explosion_loader.h"
#include <algorithm>
#include <iostream>
int main(int argc, char **argv) {
    if (argc != 7) return 2;
    sh_mdp_explosions::requested = std::string(argv[3]) == "on";
    const bool sh2 = std::string(argv[4]) == "sh2";
    markv::reject_patch = std::string(argv[5]) == "reject";
    sh_mdp_explosions::system_directory = argv[2];
    std::vector<std::uint8_t> rom(0x400000, 0xa5);
    sh_mdp_explosions::apply(rom.data(), std::stoul(argv[6]), rom.size(), sh2, argv[1]);
    if (sh_mdp_explosions::eligible != (sh2 && std::stoul(argv[6]) == 0x380000)) return 8;
    const bool changed = std::any_of(rom.begin(), rom.end(), [](auto b) { return b != 0xa5; });
    std::cout << sh_mdp_explosions::active << ' ' << int(sh_mdp_explosions::notification.load())
              << ' ' << changed << '\n';
    using namespace sh_mdp_explosions;
    std::uint8_t old_state[32] = {'M','A','M','E'};
    std::uint8_t mod_state[32]; std::memcpy(mod_state, state_tag, sizeof(state_tag));
    if (!state_matches(old_state, sizeof(old_state), false) || state_matches(old_state, sizeof(old_state), true)) return 3;
    if (!state_matches(mod_state, sizeof(mod_state), true) || state_matches(mod_state, sizeof(mod_state), false)) return 4;
    if (state_matches(mod_state, 8, true) || state_matches(mod_state, 8, false)) return 5;
    mod_state[8] = 1; // The previous published modification is incompatible.
    if (state_matches(mod_state, sizeof(mod_state), true) || state_matches(mod_state, sizeof(mod_state), false)) return 6;
    if (state_matches(nullptr, 0, false) || state_matches(nullptr, 0, true)) return 7;
}
'''

class ExplosionLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        (cls.root / 'util').mkdir()
        for name in ('sh2_explosion_options.h', 'sh2_explosion_loader.h'):
            shutil.copyfile(ROOT / 'src/markv' / name, cls.root / name)
        for name, text in [('util/corefile.h', CORE_FILE), ('util/hashing.h', HASH),
                           ('sh2_explosion_patch.h', PATCH), ('probe.cpp', PROBE)]:
            (cls.root / name).write_text(text)
        cls.probe = cls.root / ('probe.exe' if os.name == 'nt' else 'probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic', '-I', str(cls.root),
            str(cls.root / 'probe.cpp'), '-o', str(cls.probe)], check=True)

    def run_case(self, cart_donor=None, system_donor=None, option='on', game='sh2', patch='accept', size=0x380000):
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            base = Path(tmp)
            cart, system = base / 'cart', base / 'system'
            cart.mkdir(); system.mkdir()
            for directory, kind in ((cart, cart_donor), (system, system_donor)):
                if kind:
                    blob = bytes([0x5a if kind == 'valid' else 0]) * (0x3e0000 if kind != 'short' else 32)
                    (directory / 'jp_jp_space_harrier.smp').write_bytes(blob)
            result = subprocess.run([str(self.probe), str(cart / 'SH2.smp'), str(system), option,
                                     game, patch, str(size)], check=True, text=True, capture_output=True)
            return tuple(map(int, result.stdout.split()))

    def test_original_mode_and_other_games_never_read_or_apply_donor(self):
        self.assertEqual(self.run_case(cart_donor='valid', option='off'), (0, 0, 0))
        self.assertEqual(self.run_case(cart_donor='valid', game='sh1'), (0, 0, 0))
        self.assertEqual(self.run_case(cart_donor='valid', size=0x380002), (0, 0, 0))

    def test_missing_or_invalid_donor_preserves_entire_rom(self):
        self.assertEqual(self.run_case(), (0, 2, 0))
        self.assertEqual(self.run_case(cart_donor='bad-sha'), (0, 3, 0))
        self.assertEqual(self.run_case(system_donor='short'), (0, 3, 0))

    def test_valid_local_or_system_donor_activates_patch(self):
        self.assertEqual(self.run_case(cart_donor='valid'), (1, 1, 1))
        self.assertEqual(self.run_case(system_donor='valid'), (1, 1, 1))
        self.assertEqual(self.run_case(cart_donor='bad-sha', system_donor='valid'), (1, 1, 1))

    def test_rejected_partial_patch_is_transactional(self):
        self.assertEqual(self.run_case(cart_donor='valid', patch='reject'), (0, 4, 0))

if __name__ == '__main__':
    unittest.main()
