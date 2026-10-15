"""SH1 player motion follows completed game updates and survives portable saves."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PlayerMotion(unittest.TestCase):
    def compile_and_run(self, body):
        source = r'''
#include "sh1_player_motion.h"
#include <cassert>
#include <array>
#include <limits>
using namespace sh1_player_motion;
constexpr std::uint32_t player = 0xff21ac;
static bool same(const history &a, const history &b) {
    return a.owner==b.owner && a.tick==b.tick && a.age==b.age && a.span==b.span &&
        a.x[0]==b.x[0] && a.x[1]==b.x[1] && a.y[0]==b.y[0] &&
        a.y[1]==b.y[1] && a.valid==b.valid;
}
int main() {
BODY
}
'''.replace('BODY', body)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'motion.cpp'
            path.write_text(source)
            binary = Path(directory) / 'motion'
            subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
                '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT / 'src/markv'), str(path), '-o', str(binary),
            ], check=True)
            subprocess.run([str(binary)], check=True)

    def test_completed_counter_stationary_hold_reversal_and_wrap(self):
        self.compile_and_run(r'''
    history h;
    assert(!h.valid);
    h.sample(player, 100, 100, 120);
    assert(h.valid && h.owner==player && h.tick==100 && h.age==0 && h.span==1);
    assert(h.x[0]==100 && h.x[1]==100 && h.y[0]==120 && h.y[1]==120);

    // Guest RAM has already started the next loop, but its completion counter
    // still belongs to the old loop. Do not capture those coordinates early.
    h.sample(player, 100, 108, 128);
    assert(h.age==1 && h.tick==100 && h.x[0]==100 && h.x[1]==100);
    h.sample(player, 101, 108, 128);
    assert(h.age==0 && h.span==2 && h.tick==101);
    assert(h.x[0]==100 && h.x[1]==108 && h.y[0]==120 && h.y[1]==128);
    // The four presentation positions for this interval are 102,104,106,108.
    for (unsigned n=1;n<=4;++n) {
        const std::int64_t exact=std::int64_t(h.x[0])*(4-n)+std::int64_t(h.x[1])*n;
        assert(exact==std::int64_t(100+n*2)*4);
    }

    // A long stationary period is still thousands of completed game loops.
    // It must not become the measured duration of the next moving interval.
    for (std::uint32_t tick=102;tick<=2101;++tick) {
        h.sample(player, tick-1, 108, 128);
        assert(h.age==1 && h.span==2);
        h.sample(player, tick, 108, 128);
        assert(h.age==0 && h.span==2 && h.x[0]==108 && h.x[1]==108);
    }
    h.sample(player, 2101, 116, 136);
    assert(h.x[0]==108 && h.x[1]==108); // The next loop is not complete yet.
    h.sample(player, 2102, 116, 136);
    assert(h.span==2 && h.x[0]==108 && h.x[1]==116);
    // Reversal uses the immediately preceding completed position.
    h.sample(player, 2102, 100, 120);
    h.sample(player, 2103, 100, 120);
    assert(h.span==2 && h.x[0]==116 && h.x[1]==100);
    for (unsigned n=1;n<=4;++n) {
        const std::int64_t exact=std::int64_t(h.x[0])*(4-n)+std::int64_t(h.x[1])*n;
        assert(exact==std::int64_t(116-int(n)*4)*4);
    }

    // Identity changes and explicit scene/pause clears seed a fresh endpoint.
    h.sample(player+0x54, 2103, 250, 180);
    assert(h.owner==player+0x54 && h.age==0 && h.span==1 && h.x[0]==250 && h.x[1]==250);
    h.clear();
    assert(same(h, history{}));
    h.sample(player, 0xffffffffU, 30, 90);
    h.sample(player, 0xffffffffU, 31, 91);
    h.sample(player, 0, 31, 91); // Counter wrap is an ordinary completed update.
    assert(h.tick==0 && h.span==2 && h.x[0]==30 && h.x[1]==31);

    // Stalled loops hold both endpoints; saturating age cannot wrap a later
    // doubled presentation phase or turn the denominator into zero.
    h.age=max_interval;
    h.sample(player, 0, 999, 999);
    assert(h.age==max_interval && h.x[1]==31);
    h.sample(player, 1, 32, 92);
    assert(h.span==max_interval && h.age==0 && h.x[0]==31 && h.x[1]==32);
    assert(std::uint64_t(h.span)*2+2<=std::numeric_limits<std::uint32_t>::max());

    // Invalid samples are never exposed as valid motion history.
    h.sample(player|1, 2, 40, 100); assert(same(h,history{}));
    h.sample(0xffffb6, 2, 40, 100); assert(same(h,history{}));
    h.sample(player, 2, 32768, 100); assert(same(h,history{}));
    h.sample(player, 2, 40, -32769); assert(same(h,history{}));
''')

    def test_portable_footer_roundtrip_corruption_and_transactional_failure(self):
        self.compile_and_run(r'''
    history h;
    h.owner=player; h.tick=0x89abcdef; h.age=1; h.span=2;
    h.x[0]=-12; h.x[1]=160; h.y[0]=-32768; h.y[1]=32767; h.valid=true;
    std::array<std::uint8_t,state_size> bytes{};
    assert(encode(bytes.data(),bytes.size(),h));
    // Frozen protocol vector, including negative coordinates and the checksum.
    const std::array<std::uint8_t,64> expected{{
        0x53,0x48,0x31,0x50,0x4d,0x4f,0x54,0x00,0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x40,
        0x00,0xff,0x21,0xac,0x89,0xab,0xcd,0xef,0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x02,
        0xff,0xff,0xff,0xf4,0x00,0x00,0x00,0xa0,0xff,0xff,0x80,0x00,0x00,0x00,0x7f,0xff,
        0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x00,0xe1,0x5f,0xd9,0x67,0x45,0x4e,0x44,0x21
    }};
    assert(bytes==expected);
    history restored;
    assert(decode(bytes.data(),bytes.size(),restored) && same(h,restored));

    // Saving between two native refreshes preserves the measured interval and
    // every later endpoint, rather than restarting the movement after loading.
    history playback;
    playback.sample(player,10,100,120);
    playback.sample(player,10,108,128);
    assert(encode(bytes.data(),bytes.size(),playback));
    assert(decode(bytes.data(),bytes.size(),restored));
    for (unsigned i=0;i<12;++i) {
        const auto tick=11+i/2;
        playback.sample(player,tick,108-int(i)*2,128+int(i));
        restored.sample(player,tick,108-int(i)*2,128+int(i));
        assert(same(playback,restored));
    }

    const history sentinel=h;
    restored=sentinel;
    for (std::size_t size=0;size<state_size;++size) {
        assert(!decode(expected.data(),size,restored));
        assert(same(restored,sentinel));
    }
    assert(!decode(nullptr,state_size,restored) && same(restored,sentinel));
    assert(!decode(expected.data(),state_size+1,restored) && same(restored,sentinel));
    for (std::size_t i=0;i<state_size;++i) {
        auto corrupt=expected; corrupt[i]^=1;
        assert(!decode(corrupt.data(),corrupt.size(),restored));
        assert(same(restored,sentinel));
    }

    // Recompute the transport checksum to exercise semantic validation too.
    auto put=[](auto &buffer,unsigned offset,std::uint32_t value) {
        for (unsigned i=0;i<4;++i) buffer[offset+i]=std::uint8_t(value>>(24-i*8));
    };
    auto refresh=[&](auto &buffer) {
        std::uint32_t hash=2166136261U;
        for (unsigned i=0;i<64;++i)
            if (i<56 || i>=60) hash=(hash^buffer[i])*16777619U;
        put(buffer,56,hash);
    };
    struct Mutation {unsigned offset;std::uint32_t value;};
    for (const auto mutation : {
        Mutation{8,2}, Mutation{12,65}, Mutation{16,0}, Mutation{16,player|1},
        Mutation{16,0xffffb6}, Mutation{24,max_interval+1}, Mutation{28,0},
        Mutation{28,max_interval+1}, Mutation{32,32768}, Mutation{36,0xffff7fff},
        Mutation{40,32768}, Mutation{44,0xffff7fff}, Mutation{48,2},
        Mutation{48,0}, Mutation{52,1}, Mutation{60,0},
    }) {
        auto corrupt=expected;
        put(corrupt,mutation.offset,mutation.value); refresh(corrupt);
        assert(!decode(corrupt.data(),corrupt.size(),restored));
        assert(same(restored,sentinel));
    }

    history cleared;
    assert(encode(bytes.data(),bytes.size(),cleared));
    assert(decode(bytes.data(),bytes.size(),restored) && same(restored,cleared));
    auto invalid_empty=bytes; put(invalid_empty,16,player); refresh(invalid_empty);
    assert(!decode(invalid_empty.data(),invalid_empty.size(),restored));
    assert(same(restored,cleared));

    // Invalid histories and short destinations do not partially write a footer.
    bytes.fill(0xa5); const auto untouched=bytes;
    auto invalid=h; invalid.span=0;
    assert(!encode(bytes.data(),bytes.size(),invalid) && bytes==untouched);
    invalid=h; invalid.x[1]=32768;
    assert(!encode(bytes.data(),bytes.size(),invalid) && bytes==untouched);
    assert(!encode(bytes.data(),bytes.size()-1,h) && bytes==untouched);
    assert(!encode(nullptr,state_size,h));
''')


if __name__ == '__main__':
    unittest.main()
