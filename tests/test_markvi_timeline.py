"""The production presentation clock follows native emitter updates."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, full_function

class Timeline(unittest.TestCase):
    def test_measured_cadence_hold_and_invalidation(self):
        method=full_function(patched_fragments(PATCH.read_text(),'src/devices/video/315_5313.cpp'),
                             'void sega315_5313_device::sh2_markvi_begin_frame()')
        program=r'''
#include "sh2_markvi.h"
#include "sh_video_options.h"
#include <algorithm>
#include <cassert>
#include <cstring>
using u16=std::uint16_t;using u32=std::uint32_t;
struct space {
 std::vector<u16> rom=std::vector<u16>(0x200000);
 u16 read_word(u32 p){return rom[p/2];}
};
class sega315_5313_device {
public:
 int mdp_widescreen_padding() const {return 0;}
 bool m_markvi_ready[3]{false,false,true},m_markvi_history_valid=false,m_markvi_smooth_valid=false;
 u16 m_markvi_ram[3][0x10000]{},m_markvi_history[2][0x10000]{};
 unsigned m_markvi_age=0,m_markvi_span=1;
 std::vector<sh2_markvi::sprite> m_markvi_sprites,m_markvi_phases[2];
 space memory;space *m_space68k=&memory;
 void sh2_markvi_begin_frame();
 void put(u32 a,u16 v){if(a>=0xfe0000)m_markvi_ram[2][(a-0xfe0000)/2]=v;else memory.rom[a/2]=v;}
 void lng(u32 a,u32 v){put(a,v>>16);put(a+2,v);}
 void build(){assert(sh2_markvi::build([this](u32 a){return a>=0xfe0000?m_markvi_ram[2][(a-0xfe0000)/2]:memory.read_word(a);},m_markvi_sprites));}
};
METHOD
int main(){
 sega315_5313_device v;
 v.lng(0x13b78e,0xff3542);v.lng(0xff38f2,0xff5000);
 v.lng(0xff5010,0x123456);v.lng(0xff501c,0x1000);v.put(0xff502a,4);v.put(0x100a,0x100);
 v.lng(0x100c,0x2000);v.put(0xff3542,32);
 v.build();assert(v.m_markvi_sprites.size()==1);
 assert(v.m_markvi_sprites[0].routine==0x123456);
 sh_mdp_video::hz120=true;
 v.sh2_markvi_begin_frame();assert(v.m_markvi_phases[0][0].x==128);
 v.sh2_markvi_begin_frame();assert(v.m_markvi_phases[1][0].x==128);
 v.lng(0xff5000,0xabcde); // Moving world X/Y must not look like a handler change.
 v.put(0xff500c,32);v.build();v.sh2_markvi_begin_frame();
 assert(v.m_markvi_span==2);
 assert(v.m_markvi_phases[0][0].x==136 && v.m_markvi_phases[1][0].x==144);
 v.sh2_markvi_begin_frame();
 assert(v.m_markvi_phases[0][0].x==152 && v.m_markvi_phases[1][0].x==160);
 // A stalled game holds its last endpoint; it must not extrapolate.
 v.sh2_markvi_begin_frame();v.sh2_markvi_begin_frame();
 assert(v.m_markvi_phases[0][0].x==160 && v.m_markvi_phases[1][0].x==160);
 // Invalidated uploads/scene clears discard the entire history.
 v.m_markvi_ready[2]=false;v.sh2_markvi_begin_frame();
 assert(!v.m_markvi_history_valid && !v.m_markvi_smooth_valid && v.m_markvi_phases[0].empty());
 v.m_markvi_ready[2]=true;v.put(0xff500c,80);v.build();v.sh2_markvi_begin_frame();
 assert(v.m_markvi_phases[0][0].x==208);
 sh_mdp_video::hz120=false;v.sh2_markvi_begin_frame();assert(!v.m_markvi_history_valid);
}
'''.replace('METHOD',method)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(program);binary=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Werror','-I',str(PATCH.parent.parent/'src/markv'),str(p),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__':unittest.main()
