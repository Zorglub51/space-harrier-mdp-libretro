"""The host list follows producer completion, native uploads and RAM clearing."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, full_function

class MarkVILifecycle(unittest.TestCase):
    def test_complete_banks_and_external_clears(self):
        source=patched_fragments(PATCH.read_text(),'src/devices/video/315_5313.cpp')
        methods='\n'.join(full_function(source,signature) for signature in (
            'void sega315_5313_device::sh2_markvi_capture()',
            'void sega315_5313_device::sh2_markvi_finalize()',
            'void sega315_5313_device::sh2_markvi_rebuild()',
            'void sega315_5313_device::sh2_markvi_dma(u32 source, u32 address, u32 count)'))
        program=r'''
#include "sh2_markvi.h"
#include <algorithm>
#include <array>
#include <cassert>
using u16=std::uint16_t;using u32=std::uint32_t;
struct space {
 std::array<u16,0x10000> ram{};
 u16 *get_read_ptr(u32 p){return p>=0xfe0000&&p<=0xfffffe?&ram[(p-0xfe0000)/2]:nullptr;}
 u16 read_word(u32){return 0;}
};
class sega315_5313_device {
public:
 bool m_sh2_text_compat=true;
 u16 m_regs[64]{},m_vdp_code=0x21;
 u16 m_markvi_ram[3][0x10000]{};
 bool m_markvi_ready[3]{};
 u32 m_markvi_source[2]{};
 u16 m_markvi_sat[2][0x140]{};
 int m_markvi_build_bank=-1;
 std::vector<sh2_markvi::sprite> m_markvi_sprites;
 space memory;space *m_space68k=&memory;
 void sh2_markvi_capture();void sh2_markvi_finalize();void sh2_markvi_rebuild();
 void sh2_markvi_dma(u32,u32,u32);
};
METHODS
int main(){
 sega315_5313_device v;
 v.m_regs[5]=0x70;
 auto &r=v.memory.ram;
 r[(0xff0e00-0xfe0000)/2]=0xff;r[(0xff0e02-0xfe0000)/2]=0x415e;
 r[0]=0x1234;
 v.sh2_markvi_capture();
 v.sh2_markvi_dma(0xff415e,0xe000,0x140);assert(!v.m_markvi_ready[2]);
 // Capture holds producer-entry state, even when the live world moves on.
 r[0]=0x5678;v.sh2_markvi_finalize();v.sh2_markvi_dma(0xff415e,0xe000,0x140);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x1234&&r[0]==0x5678);
 // Re-linking the native list doesn't invalidate its geometry.
 const auto head=(0xff415e - 0xfe0000)/2;
 r[head+1]=40;v.sh2_markvi_dma(0xff415e,0xe000,0x140);assert(v.m_markvi_ready[2]);
 // Replacing a bank without running the constructor must not resurrect it.
 r[head+2]=42;v.sh2_markvi_dma(0xff415e,0xe000,0x140);assert(!v.m_markvi_ready[2]);
 v.sh2_markvi_capture();v.sh2_markvi_finalize();v.sh2_markvi_dma(0xff415e,0xe000,0x140);
 assert(v.m_markvi_ready[2]);
 v.sh2_markvi_dma(0xff415e,0xe000,4);assert(!v.m_markvi_ready[2]);
 // The other producer bank has an independent lifetime and snapshot.
 r[(0xff387c-0xfe0000)/2]=1;v.sh2_markvi_capture();v.sh2_markvi_finalize();
 v.sh2_markvi_dma(0xff3080,0xe000,0x140);assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x5678);
 v.sh2_markvi_dma(0xff6000,0xe000,0x140);assert(!v.m_markvi_ready[2]);
}
'''.replace('METHODS',methods)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(program);exe=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Werror','-I',str(PATCH.parent.parent/'src/markv'),str(p),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=='__main__':unittest.main()
