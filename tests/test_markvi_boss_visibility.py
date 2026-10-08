"""Trace the native boss's two hide reasons without changing guest state."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, full_function


class BossVisibility(unittest.TestCase):
    def test_executed_branches_and_private_snapshot(self):
        patch = PATCH.read_text()
        vdp = patched_fragments(patch, 'src/devices/video/315_5313.cpp')
        driver = patched_fragments(patch, 'src/mame/sega/mdconsole.cpp')
        setter = full_function(vdp, 'void sega315_5313_device::sh2_markvi_boss_visibility(u32 object, bool budget)')
        observer = full_function(driver, '[this, site](offs_t offset, u16 &data, u16 mem_mask)')
        code = r'''
#include "sh2_markvi.h"
#include <array>
#include <cassert>
using u16=std::uint16_t;using u32=std::uint32_t;using offs_t=u32;
enum {M68K_D4,M68K_A0};
struct cpu {u32 instruction=0,d4=0,a0=0xff5000;u32 pc(){return instruction;}
 u32 state_int(unsigned r){return r==M68K_D4?d4:a0;}};
struct machine_state {bool disabled=false;bool side_effects_disabled(){return disabled;}};
struct sega315_5313_device {
 bool m_sh2_text_compat=true;bool m_markvi_boss_budget[0x8000]{};
 void sh2_markvi_boss_visibility(u32,bool);
};
SETTER
struct driver {
 cpu proc;cpu *m_maincpu=&proc;sega315_5313_device v;sega315_5313_device *m_vdp=&v;
 machine_state state;machine_state &machine(){return state;}
 auto tap(u32 site){return OBSERVER;}
 void execute(u32 site,u32 d4){proc.instruction=site;proc.d4=d4;u16 data=0x1234;
  tap(site)(site,data,0xffff);assert(data==0x1234);}
};
int main(){
 driver d;auto &marked=d.v.m_markvi_boss_budget[0x5000/2];
 d.execute(0x16d774,1);assert(marked); // Nearby odd segment: display budget.
 d.execute(0x16d832,2);assert(!marked); // Coincident trailing segment: keep hidden.
 d.execute(0x16d774,3);assert(marked);
 d.execute(0x16d778,0);assert(!marked); // Native clear path.
 d.execute(0x16d774,2);assert(!marked);
 d.state.disabled=true;d.execute(0x16d774,1);assert(!marked);d.state.disabled=false;
 d.proc.instruction=0;d.proc.d4=1;u16 data=0;d.tap(0x16d774)(0,data,0xffff);assert(!marked);
 d.v.m_sh2_text_compat=false;d.execute(0x16d774,1);assert(!marked);d.v.m_sh2_text_compat=true;
 d.proc.a0=0xff5001;d.execute(0x16d774,1);assert(!marked);
 d.proc.a0=0xffffb6;d.execute(0x16d774,1);
 d.proc.a0=0xfe5000;d.execute(0x16d774,1);
 std::array<u16,0x10000> guest{};
 auto object=[&](u32 a){auto p=guest.data()+(a - 0xfe0000)/2;
  p[8]=0x16;p[9]=0xd6ea;p[14]=0;p[15]=0x17c4;p[21]=0x1282;};
 object(0xff5000);object(0xff5100);object(0xffffb4);
 d.proc.a0=0xff5000;d.execute(0x16d774,1);
 d.proc.a0=0xff5100;d.execute(0x16d832,2);
 d.proc.a0=0xffffb4;d.execute(0x16d774,1);
 auto snapshot=guest;sh2_markvi::clear_traced_boss_budget(snapshot.data(),d.v.m_markvi_boss_budget);
 assert(guest[(0xff502a - 0xfe0000)/2]==0x1282);
 assert(snapshot[(0xff502a - 0xfe0000)/2]==0x1202);
 assert(snapshot[(0xff512a - 0xfe0000)/2]==0x1282);
 assert(snapshot[(0xffffde - 0xfe0000)/2]==0x1202);
 // Reused slots with another handler/artwork must retain their own masks.
 guest[(0xff5012 - 0xfe0000)/2]=0xd840;
 snapshot=guest;sh2_markvi::clear_traced_boss_budget(snapshot.data(),d.v.m_markvi_boss_budget);
 assert(snapshot[(0xff502a - 0xfe0000)/2]==0x1282);
 guest[(0xff5012 - 0xfe0000)/2]=0xd6ea;guest[(0xff501e - 0xfe0000)/2]=0x17c6;
 snapshot=guest;sh2_markvi::clear_traced_boss_budget(snapshot.data(),d.v.m_markvi_boss_budget);
 assert(snapshot[(0xff502a - 0xfe0000)/2]==0x1282);
}
'''.replace('SETTER', setter).replace('OBSERVER', observer)
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'probe.cpp';binary=Path(temp)/'probe';source.write_text(code)
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Wno-unused-parameter','-Werror',
                '-I',str(PATCH.parent.parent/'src/markv'),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__':unittest.main()
