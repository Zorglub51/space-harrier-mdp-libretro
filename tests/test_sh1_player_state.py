"""Compile the production libretro state boundary with a small native payload.

No ROM or MAME build is needed. The native buffer API records its exact pointer,
length and calls, so rejected SH1 footers cannot silently mutate the machine.
The existing SH2 explosion envelopes are exercised through the same functions.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments


ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''
#include <array>
#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>
#include "sh_video_options.h"
#include "sh2_explosion_options.h"
using u8 = std::uint8_t;
enum save_error { STATERR_NONE, STATERR_NOT_FOUND, STATERR_INVALID_HEADER };
constexpr int RETRO_LOG_ERROR = 1;
void log_cb(int, const char *, ...) {}
bool same(const sh1_player_motion::history &a, const sh1_player_motion::history &b) {
    return a.owner==b.owner && a.tick==b.tick && a.age==b.age && a.span==b.span &&
        a.x[0]==b.x[0] && a.x[1]==b.x[1] && a.y[0]==b.y[0] && a.y[1]==b.y[1] &&
        a.valid==b.valid;
}
sh1_player_motion::history motion(unsigned tick=17) {
    sh1_player_motion::history h;
    h.sample(0xff21ac,tick,160,144);
    h.sample(0xff21ac,tick,168,136);
    h.sample(0xff21ac,tick+1,168,136);
    h.sample(0xff21ac,tick+1,176,128);
    return h;
}
struct FakeSave {
    static constexpr std::size_t payload = 37;
    std::array<u8,payload> memory{};
    unsigned writes=0,reads=0;
    std::size_t size=payload,last_size=0;
    const void *last_pointer=nullptr;
    bool fail_read=false,clear_history_on_read=false;
    sh1_player_motion::history history_at_read;
    FakeSave() {
        for(unsigned i=0;i<memory.size();++i) memory[i]=u8(i*7+3);
        std::memcpy(memory.data(),"MAME",4);
    }
    save_error write_buffer(u8 *data,std::size_t length) {
        ++writes;last_pointer=data;last_size=length;
        if(!data || length!=memory.size()) return STATERR_INVALID_HEADER;
        std::memcpy(data,memory.data(),length);
        return STATERR_NONE;
    }
    save_error read_buffer(u8 *data,std::size_t length) {
        ++reads;last_pointer=data;last_size=length;
        history_at_read=sh1_player_motion::state;
        if(fail_read || !data || length!=memory.size() || std::memcmp(data,"MAME",4))
            return STATERR_INVALID_HEADER;
        std::memcpy(memory.data(),data,length);
        // Native post-load callbacks may clear transient renderer state. The
        // presentation footer must be committed after a successful native load.
        if(clear_history_on_read) sh_mdp_video::clear_pending();
        return STATERR_NONE;
    }
};
struct FakeMachine { FakeSave state; FakeSave &save(){return state;} } machine;
bool manager_present=true,machine_present=true;
struct mame_machine_manager {
    static mame_machine_manager *instance() {
        static mame_machine_manager manager;
        return manager_present ? &manager : nullptr;
    }
    FakeMachine *machine(){return machine_present ? &::machine : nullptr;}
};
namespace ram_state { std::size_t get_size(FakeSave &save){return save.size;} }
FUNCTIONS
constexpr std::size_t P=FakeSave::payload,F=sh1_player_motion::state_size;
void reset(unsigned profile=1) {
    machine.state=FakeSave{};manager_present=machine_present=true;
    sh_mdp_explosions::active=false;sh_mdp_explosions::eligible=false;
    sh_mdp_video::set_game(profile);
    sh1_player_motion::state=motion();
}
std::vector<u8> save() {
    std::vector<u8> bytes(retro_serialize_size());
    assert(retro_serialize(bytes.data(),bytes.size()));
    return bytes;
}
void modes() {
    reset();
    for(auto mode:{sh_mdp_video::rendering::original,sh_mdp_video::rendering::mark_vi,
                  sh_mdp_video::rendering::mark_vi_120}) {
        sh_mdp_video::sh1_rendering=mode;sh_mdp_video::apply_rendering_options();
        assert(retro_serialize_size()==P+64);
        const auto expected_history=sh1_player_motion::state;
        const auto expected_payload=machine.state.memory;
        std::vector<u8> bytes(P+F+2,0xa5);
        assert(retro_serialize(bytes.data(),P+F));
        assert(machine.state.last_pointer==bytes.data() && machine.state.last_size==P);
        assert(std::equal(expected_payload.begin(),expected_payload.end(),bytes.begin()));
        assert(std::memcmp(bytes.data()+P,"SH1PMOT\0",8)==0);
        sh1_player_motion::history restored;
        assert(sh1_player_motion::decode(bytes.data()+P,F,restored));
        assert(same(restored,expected_history));
        assert(bytes[P+F]==0xa5 && bytes[P+F+1]==0xa5);
        const auto untouched=bytes;
        const unsigned writes=machine.state.writes;
        assert(!retro_serialize(bytes.data(),P+F-1) && machine.state.writes==writes);
        assert(bytes==untouched);
        assert(!retro_serialize(nullptr,P+F) && machine.state.writes==writes);
        sh1_player_motion::state.span=0;
        assert(!retro_serialize(bytes.data(),P+F) && machine.state.writes==writes);
        assert(bytes==untouched);
        sh1_player_motion::state=expected_history;
    }
    reset(0);assert(retro_serialize_size()==P);
    assert(save().size()==P && machine.state.last_size==P);
    reset();manager_present=false;assert(retro_serialize_size()==0);
    assert(!retro_serialize(nullptr,0));
    manager_present=true;machine_present=false;assert(retro_serialize_size()==0);
    assert(!retro_serialize(nullptr,0));
    machine_present=true;machine.state.size=0;assert(retro_serialize_size()==0);
    assert(!retro_serialize(nullptr,0));
}
void loading() {
    reset();const auto saved_history=sh1_player_motion::state;
    auto bytes=save();const auto payload=machine.state.memory;
    const auto sentinel=motion(1000);
    sh1_player_motion::state=sentinel;
    machine.state.memory[8]^=0xff;
    machine.state.clear_history_on_read=true;
    assert(retro_unserialize(bytes.data(),bytes.size()));
    assert(machine.state.last_pointer==bytes.data() && machine.state.last_size==P);
    assert(same(machine.state.history_at_read,sentinel));
    assert(machine.state.memory==payload && same(sh1_player_motion::state,saved_history));
    // A v0.1.23 payload has no footer: load its native bytes and seed a fresh
    // player history on the next completed game update.
    sh1_player_motion::state=sentinel;
    assert(retro_unserialize(bytes.data(),P));
    assert(machine.state.last_size==P && same(sh1_player_motion::state,{}));
    // A valid footer cannot be committed when native MAME rejects its payload.
    sh1_player_motion::state=sentinel;machine.state.fail_read=true;
    const auto before=machine.state.memory;
    assert(!retro_unserialize(bytes.data(),bytes.size()));
    assert(same(sh1_player_motion::state,sentinel) && machine.state.memory==before);
    assert(same(machine.state.history_at_read,sentinel));
    machine.state.fail_read=false;bytes[0]^=1;
    assert(!retro_unserialize(bytes.data(),bytes.size()));
    assert(same(sh1_player_motion::state,sentinel) && machine.state.memory==before);
}
void rejection() {
    reset();const auto bytes=save();const auto before=machine.state.memory;
    const auto sentinel=motion(1000);sh1_player_motion::state=sentinel;
    const unsigned reads=machine.state.reads;
    const auto rejected=[&](const void *data,std::size_t length) {
        assert(!retro_unserialize(data,length));
        assert(machine.state.reads==reads && machine.state.memory==before);
        assert(same(sh1_player_motion::state,sentinel));
    };
    rejected(nullptr,P);rejected(nullptr,P+F);
    for(std::size_t length=0;length<P+F+4;++length)
        if(length!=P && length!=P+F) rejected(bytes.data(),length);
    // Every footer byte is authenticated, including its type/version/length,
    // endpoint values, reserved fields, checksum and end marker.
    for(std::size_t i=P;i<P+F;++i) {
        auto corrupt=bytes;corrupt[i]^=1;rejected(corrupt.data(),corrupt.size());
    }
    // Empty histories are represented explicitly; arbitrary zero padding from
    // another format cannot be mistaken for a valid new SH1 footer.
    auto zeros=bytes;std::fill(zeros.begin()+P,zeros.end(),0);
    rejected(zeros.data(),zeros.size());
    // Even with a valid footer, no MAME machine means no history restoration.
    manager_present=false;assert(!retro_unserialize(bytes.data(),bytes.size()));
    assert(same(sh1_player_motion::state,sentinel));manager_present=true;
    machine_present=false;assert(!retro_unserialize(bytes.data(),bytes.size()));
    assert(same(sh1_player_motion::state,sentinel));machine_present=true;
    machine.state.size=0;assert(!retro_unserialize(bytes.data(),bytes.size()));
    assert(same(sh1_player_motion::state,sentinel));
}
void sh2() {
    reset(2);sh_mdp_explosions::eligible=true;
    const auto original_payload=machine.state.memory;
    const auto sentinel=sh1_player_motion::state;
    constexpr auto E=sizeof(sh_mdp_explosions::state_tag);
    assert(retro_serialize_size()==P+E);
    const auto original=save();
    assert(std::equal(original_payload.begin(),original_payload.end(),original.begin()));
    assert(std::all_of(original.begin()+P,original.end(),[](u8 b){return b==0;}));
    assert(machine.state.last_pointer==original.data() && machine.state.last_size==P);
    assert(retro_unserialize(original.data(),original.size()));
    assert(retro_unserialize(original.data(),P));
    assert(same(sh1_player_motion::state,sentinel));
    auto bad_padding=original;bad_padding.back()=1;
    unsigned reads=machine.state.reads;
    assert(!retro_unserialize(bad_padding.data(),bad_padding.size()));
    assert(!retro_unserialize(original.data(),P+E-1) && machine.state.reads==reads);
    sh_mdp_explosions::active=true;
    assert(retro_serialize_size()==P+E);
    const auto patched=save();
    assert(std::memcmp(patched.data(),sh_mdp_explosions::state_tag,E)==0);
    assert(std::equal(original_payload.begin(),original_payload.end(),patched.begin()+E));
    assert(machine.state.last_pointer==patched.data()+E && machine.state.last_size==P);
    reads=machine.state.reads;
    assert(!retro_unserialize(original.data(),original.size()) && machine.state.reads==reads);
    assert(retro_unserialize(patched.data(),patched.size()));
    assert(machine.state.last_pointer==patched.data()+E && machine.state.last_size==P);
    assert(same(sh1_player_motion::state,sentinel));
    reads=machine.state.reads;
    assert(!retro_unserialize(patched.data(),P+E-1) && machine.state.reads==reads);
    auto version=patched;version[8]=2;
    assert(!retro_unserialize(version.data(),version.size()) && machine.state.reads==reads);
    sh_mdp_explosions::active=false;
    assert(!retro_unserialize(patched.data(),patched.size()) && machine.state.reads==reads);
    sh_mdp_explosions::eligible=false;assert(retro_serialize_size()==P);
    assert(save().size()==P);
}
int main(int argc,char **argv) {
    assert(argc==2);
    if(!std::strcmp(argv[1],"modes")) modes();
    else if(!std::strcmp(argv[1],"loading")) loading();
    else if(!std::strcmp(argv[1],"rejection")) rejection();
    else if(!std::strcmp(argv[1],"sh2")) sh2();
    else return 2;
    std::cout << argv[1] << " passed\n";
}
'''


class PlayerState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        cpp = patched_fragments(PATCH.read_text(), 'src/osd/libretro/libretro-internal/libretro.cpp')
        functions = '\n'.join(full_function(cpp, signature) for signature in (
            'size_t retro_serialize_size(void)',
            'bool retro_serialize(void *data, size_t size)',
            'bool retro_unserialize(const void *data, size_t size)',
        ))
        source = directory / 'state.cpp'
        source.write_text(PROBE.replace('FUNCTIONS', functions), encoding='utf-8')
        cls.probe = directory / ('probe.exe' if os.name == 'nt' else 'probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic',
            '-I', str(ROOT / 'src/markv'), str(source), '-o', str(cls.probe),
        ], check=True)

    def run_case(self, case):
        result = subprocess.run([str(self.probe), case], text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.strip(), f'{case} passed')

    def test_size_and_exact_native_payload_in_every_sh1_mode(self):
        self.run_case('modes')

    def test_new_and_legacy_states_commit_history_after_native_success(self):
        self.run_case('loading')

    def test_bad_footer_or_length_never_reaches_native_loader(self):
        self.run_case('rejection')

    def test_sh2_original_and_patched_state_formats_are_unchanged(self):
        self.run_case('sh2')


if __name__ == '__main__':
    unittest.main()
