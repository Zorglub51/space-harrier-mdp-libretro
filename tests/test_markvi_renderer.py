"""Compile and exercise the production dynamic-list pixel path."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, full_function

class MarkVIRenderer(unittest.TestCase):
    def test_long_lists_zoom_priority_and_empty_frame(self):
        method=full_function(patched_fragments(PATCH.read_text(),'src/devices/video/315_5313.cpp'),
                             'bool sega315_5313_device::mdp_render_markvi_spriteline(int scanline)')
        source=r'''
#include "sh2_markvi.h"
#include "sh1_markvi.h"
#include "sh_markvi_profile.h"
#include "sh_video_options.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <memory>
using u8=std::uint8_t;using u16=std::uint16_t;using u32=std::uint32_t;
#define BIT(v,b) (((v)>>(b))&1U)
class sega315_5313_device {
public:
 int padding=0;
 int mdp_widescreen_padding() const {return padding;}
 unsigned m_markvi_game=2;
 bool m_sh2_text_compat=true,m_markvi_ready[3]={false,false,true};
 u16 m_regs[64]{};
 std::array<u16,65536> vram{};
 std::vector<sh2_markvi::sprite> m_markvi_sprites;
 std::unique_ptr<u16[]> m_sprite_renderline=std::make_unique<u16[]>(1024);
 u16 mdp_vram_word(u32 address)const{return vram[address&65535];}
 bool mdp_render_markvi_spriteline(int scanline);
};
METHOD
int main(){
 sega315_5313_device v;
 v.m_regs[12]=0x81;v.m_regs[36]=0x91;
 sh_mdp_video::markvi=true;
 std::fill_n(v.vram.begin()+16,16,0x1111);
 std::fill_n(v.vram.begin()+32,16,0x2222);
 // All 600 entries share a scanline; only the last is on screen.
 v.m_markvi_sprites.assign(599,{128,0,1,511,4096});
 v.m_markvi_sprites.push_back({128,0,2,228,4096});
 assert(v.mdp_render_markvi_spriteline(0));
 for(unsigned i=0;i<1024;++i)assert(v.m_sprite_renderline[i]==(i>=228&&i<236?0x42:0));
 // The 600th entry has its own transform, with no 7-bit index wrap.
 v.m_markvi_sprites.back().zoom=2048;
 v.mdp_render_markvi_spriteline(0);
 for(unsigned i=0;i<1024;++i)assert(v.m_sprite_renderline[i]==(i>=228&&i<232?0x42:0));
 // Earlier sprites win overlaps. Empty frames have no persistent pixels.
 v.m_markvi_sprites.insert(v.m_markvi_sprites.begin(),{128,0,1,228,4096});
 v.mdp_render_markvi_spriteline(0);assert(v.m_sprite_renderline[228]==0x41);
 // Mark VI clips shrunken tiles at the viewport boundary rather than
 // dropping an entire cell crossing the former 4:3 left edge. Both games and
 // horizontal orientations keep the visible pixels, including in 16:9.
 for(unsigned game : {1U,2U})for(int padding : {0,53})for(int flip : {0,0x800}) {
  v.m_markvi_game=game;v.padding=padding;
  for(int scale : {2048,4096}) {
   v.m_markvi_sprites={{128,0,u16(1|flip),126,u16(scale)}};
   assert(v.mdp_render_markvi_spriteline(0));
   const int first=padding ? 126 : 128;
   const int end=scale==2048 ? 130 : 134;
   for(int i=0;i<1024;++i)
    assert(v.m_sprite_renderline[i]==(i>=first&&i<end ? 0x41 : 0));
  }
 }
 v.padding=0;v.m_markvi_game=2;
 v.m_markvi_sprites.clear();v.mdp_render_markvi_spriteline(0);
 for(unsigned i=0;i<1024;++i)assert(!v.m_sprite_renderline[i]);
 v.m_markvi_sprites.push_back({128,0,1,228,0});
 v.mdp_render_markvi_spriteline(0); // Zero height must not divide by zero.
 assert(!v.m_sprite_renderline[228]);
 sh_mdp_video::markvi=false;assert(!v.mdp_render_markvi_spriteline(0));
 sh_mdp_video::markvi=true;v.m_markvi_game=0;assert(!v.mdp_render_markvi_spriteline(0));
}
'''.replace('METHOD',method)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(source);binary=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Werror','-I',str(PATCH.parent.parent/'src/markv'),str(p),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__':unittest.main()
