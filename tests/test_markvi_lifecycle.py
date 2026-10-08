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
            'void sega315_5313_device::sh2_markvi_dma(u32 source, u32 address, u32 count, bool was_active)'))
        program=r'''
#include "sh2_markvi.h"
#include <algorithm>
#include <array>
#include <cassert>
using u16=std::uint16_t;using u32=std::uint32_t;
struct space {
 std::array<u16,0x10000> ram{};
 u16 *get_read_ptr(u32 p){return p>=0xfe0000&&p<=0xfffffe?&ram[(p-0xfe0000)/2]:nullptr;}
 u16 read_word(u32 p){auto q=get_read_ptr(p);return q?*q:0;}
};
class sega315_5313_device {
public:
 int mdp_widescreen_padding() const {return 0;}
 bool m_sh2_text_compat=true, m_markvi_smooth_valid=false;
 u16 m_regs[64]{},m_vdp_code=0x21;
 u16 m_markvi_ram[3][0x10000]{};
 bool m_markvi_boss_budget[0x8000]{};
 bool m_markvi_ready[3]{};
 u32 m_markvi_source[3]{};
 u16 m_markvi_sat[3][0x140]{};
 u16 m_markvi_tail[3][0x141]{};
 u16 vram[0x10000]{};
 u16 mdp_vram_word(u32 p){return vram[p & 0xffff];}
 int m_markvi_build_bank=-1;
 std::vector<sh2_markvi::sprite> m_markvi_sprites;
 space memory;space *m_space68k=&memory;
 void sh2_markvi_capture();void sh2_markvi_finalize();void sh2_markvi_rebuild();
 void sh2_markvi_dma(u32,u32,u32,bool was_active=false);
};
METHODS
int main(){
 sega315_5313_device v;
 v.m_regs[5]=0x70;v.m_regs[15]=2;
 auto &r=v.memory.ram;
 r[(0xff0e00-0xfe0000)/2]=0xff;r[(0xff0e02-0xfe0000)/2]=0x415e;
 r[0]=0x1234;
 v.sh2_markvi_capture();
 v.sh2_markvi_dma(0xff415e,0xe000,0x140);assert(!v.m_markvi_ready[2]);
 // Capture holds producer-entry state, even when the live world moves on.
 r[0]=0x5678;v.sh2_markvi_finalize();v.sh2_markvi_dma(0xff415e,0xe000,0x140);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x1234&&r[0]==0x5678);
 // The following-refresh overflow partition is already represented by the
 // unbounded host list. Keep the displayed snapshot while its producer starts
 // another build; reject modified geometry, destinations and external clears.
 r[(0xff140a-0xfe0000)/2]=1;
 r[(0xff118a-0xfe0000)/2]=0x88;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();
 auto upload=[&](u32 source,u32 address,u32 count){
  const bool active=v.m_markvi_ready[2];v.m_markvi_ready[2]=false;
  for(u32 i=0;i<count;++i)v.vram[(address/2+i)&0xffff]=v.memory.read_word(source+i*2);
  v.sh2_markvi_dma(source,address,count,active);
 };
 upload(0xff415e,0xe000,0x140);assert(v.m_markvi_ready[2]);
 v.sh2_markvi_capture();assert(!v.m_markvi_ready[0]);
 upload(0xff118a,0xe278,4);assert(v.m_markvi_ready[2]);
 assert(v.m_markvi_ram[2][0]==0x5678);
 r[(0xff118a-0xfe0000)/2]=0x99;
 upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);
 r[(0xff118a-0xfe0000)/2]=0x88;
 upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);
 v.sh2_markvi_finalize();upload(0xff415e,0xe000,0x140);
 upload(0xff118a,0xe270,4);assert(!v.m_markvi_ready[2]);
 upload(0xff415e,0xe000,0x140);
 v.vram[0xe000/2]=42;upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);
 upload(0xff415e,0xe000,0x140);
 v.m_regs[15]=4;upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);v.m_regs[15]=2;
 // The overflow can occupy the entire native 80-entry SAT.
 r[(0xff140a-0xfe0000)/2]=80;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();upload(0xff415e,0xe000,0x140);
 upload(0xff118a,0xe000,0x140);assert(v.m_markvi_ready[2]);
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
 // At higher CPU clocks the same producer finishes another generation
 // before its overflow DMA. Its authenticated tail may have another count,
 // but must not replace or retime the displayed complete host snapshot.
 r[(0xff387c-0xfe0000)/2]=0;r[0]=0x1234;
 r[(0xff140a-0xfe0000)/2]=1;r[(0xff118a-0xfe0000)/2]=0x88;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();upload(0xff415e,0xe000,0x140);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x1234);
 v.m_markvi_smooth_valid=true;
 v.m_markvi_sprites.push_back({128,0,1,128,0x1000});
 r[0]=0x5678;r[(0xff140a-0xfe0000)/2]=2;r[(0xff118a-0xfe0000)/2]=0x99;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();
 upload(0xff118a,0xe270,8);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x1234);
 assert(v.m_markvi_smooth_valid&&v.m_markvi_sprites.size()==1);
 assert(v.m_markvi_tail[2][0x140]==1); // Keep the active generation intact.
 // Neither a wrong count nor a modified prefix is authenticated by the newer tail.
 upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);
 upload(0xff415e,0xe000,0x140);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x5678);
 r[0]=0x9abc;r[(0xff140a-0xfe0000)/2]=3;r[(0xff118a-0xfe0000)/2]=0xaa;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();
 v.vram[0xe000/2]^=1;upload(0xff118a,0xe268,12);assert(!v.m_markvi_ready[2]);
 upload(0xff415e,0xe000,0x140);
 // A subsequent unfinished producer or arbitrary RAM edit still cannot pass.
 r[(0xff118a-0xfe0000)/2]=0xbb;v.sh2_markvi_capture();
 upload(0xff118a,0xe268,12);assert(!v.m_markvi_ready[2]);
 v.sh2_markvi_finalize();upload(0xff415e,0xe000,0x140);
 r[(0xff118a-0xfe0000)/2]=0xcc;
 upload(0xff118a,0xe268,12);assert(!v.m_markvi_ready[2]);
 // The opposite bank supports a completed generation with fewer pieces,
 // but an overflow from the other bank must not authenticate that frame.
 r[(0xff387c-0xfe0000)/2]=1;r[0]=0x1111;
 r[(0xff168c-0xfe0000)/2]=2;r[(0xff140c-0xfe0000)/2]=0x11;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();upload(0xff3080,0xe000,0x140);
 r[0]=0x2222;r[(0xff168c-0xfe0000)/2]=1;r[(0xff140c-0xfe0000)/2]=0x22;
 v.sh2_markvi_capture();v.sh2_markvi_finalize();upload(0xff140c,0xe278,4);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x1111);
 upload(0xff118a,0xe278,4);assert(!v.m_markvi_ready[2]);
 upload(0xff3080,0xe000,0x140);
 assert(v.m_markvi_ready[2]&&v.m_markvi_ram[2][0]==0x2222);
}
'''.replace('METHODS',methods)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(program);exe=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Werror','-I',str(PATCH.parent.parent/'src/markv'),str(p),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=='__main__':unittest.main()
