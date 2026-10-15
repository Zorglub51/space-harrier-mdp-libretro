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
 // A four-piece, 16x16 drawing exercises exact player origins, both flips,
 // tile sampling and shared boundaries between independently emitted pieces.
 // Its pixels vary on both axes, so coverage alone cannot hide a row error.
 auto art=[](unsigned tile,int x,int y)->u16 {return 1+(tile+x+y*3)%15;};
 for(unsigned tile=20;tile<24;++tile)for(int y=0;y<8;++y) {
  u32 bits=0;
  for(int x=0;x<8;++x)bits=(bits<<4)|art(tile,x,y);
  v.vram[tile*16+y*2]=bits>>16;
  v.vram[tile*16+y*2+1]=bits;
 }
 auto assembly=[&](std::int64_t origin_x,std::int64_t origin_y,unsigned d,
                   unsigned flip,bool precise) {
  std::vector<sh2_markvi::sprite> pieces;
  for(unsigned i=0;i<4;++i) {
   const int column=(flip&0x800)?1-int(i%2):int(i%2);
   const int row=(flip&0x1000)?1-int(i/2):int(i/2);
   sh2_markvi::sprite s{u16(origin_y/d+row*8),0,u16((20+i)|flip),
                       u16(origin_x/d+column*8),0x1000};
   if(precise) {
    // Deliberately different native coordinates prove the raster consumes
    // the exact presentation origin on both axes rather than the old fields.
    s.x=400+column*8;s.y=400+row*8;
    s.precise_x=origin_x+column*8*d;s.precise_y=origin_y+row*8*d;
    s.position_divisor=d;
   }
   pieces.push_back(s);
  }
  return pieces;
 };
 v.m_markvi_game=1;
 // Integral rational coordinates must retain every native pixel exactly.
 for(int padding:{0,53})for(unsigned flip:{0,0x800,0x1000,0x1800})
 for(int x:{-2,0,3})for(int y:{-2,0,3}) {
  v.padding=padding;
  const auto native=assembly((128+x)*4,(128+y)*4,4,flip,false);
  const auto precise=assembly((128+x)*4,(128+y)*4,4,flip,true);
  for(int line=0;line<22;++line) {
   v.m_markvi_sprites=native;v.mdp_render_markvi_spriteline(line);
   std::array<u16,1024> expected{};
   std::copy_n(v.m_sprite_renderline.get(),1024,expected.begin());
   v.m_markvi_sprites=precise;v.mdp_render_markvi_spriteline(line);
   for(unsigned i=0;i<1024;++i)assert(v.m_sprite_renderline[i]==expected[i]);
  }
 }
 // The independent oracle samples a single coherent 16x16 picture at each
 // output pixel centre. It does not split the picture into hardware pieces.
 // Include quarter/half/three-quarter positions in both directions, at and
 // across the left/top viewport edges, with every combination of native flips.
 for(int padding:{0,53})for(unsigned flip:{0,0x800,0x1000,0x1800})
 for(int base:{-2,0,3})for(int fx=-3;fx<=3;++fx)for(int fy=-3;fy<=3;++fy) {
  v.padding=padding;
  const int origin_x=(base+128)*4+fx,origin_y=(base+128)*4+fy;
  v.m_markvi_sprites=assembly(origin_x,origin_y,4,flip,true);
  for(int line=0;line<22;++line) {
   v.mdp_render_markvi_spriteline(line);
   for(int i=0;i<1024;++i) {
    const int x=i-128;
    const int local_x=(2*(x+128)+1)*4-2*origin_x;
    const int local_y=(2*(line+128)+1)*4-2*origin_y;
    u16 expected=0;
    if(x>=-padding&&x<320+padding&&local_x>=0&&local_x<16*8&&
       local_y>=0&&local_y<16*8) {
     int sx=local_x/8,sy=local_y/8;
     if(flip&0x800)sx=15-sx;
     if(flip&0x1000)sy=15-sy;
     expected=0x40|art(20+(sy/8)*2+sx/8,sx%8,sy%8);
    }
    assert(v.m_sprite_renderline[i]==expected);
   }
  }
 }
 // A precise zero-height sprite also reaches the height check before any
 // division, even when its rational origin covers the first scanline.
 v.padding=0;
 v.m_markvi_sprites={{200,0,20,200,0}};
 v.m_markvi_sprites[0].precise_x=128*4+1;
 v.m_markvi_sprites[0].precise_y=128*4+1;
 v.m_markvi_sprites[0].position_divisor=4;
 v.mdp_render_markvi_spriteline(0);
 for(unsigned i=0;i<1024;++i)assert(v.m_sprite_renderline[i]==0);
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
