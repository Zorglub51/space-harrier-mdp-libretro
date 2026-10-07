"""Exercise the production wide raster with synthetic tiles, without game ROMs.

The original 320-pixel buffers are deliberately absent from this mock: the
lateral renderer must never alter them. Coordinate assertions cover the two
new edges, per-line/affine transforms, signed steps, wrapping/clamping, ordinary
plane scrolling, sprite priority and display-off clearing.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments


PROBE = r"""

#include <algorithm>
#include <cstdint>
#include <cassert>
#include <cstring>
#include <iostream>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s16=int16_t;using s32=int32_t;
#define BIT(v,b) (((v)>>(b))&1U)
#define MEGADRIVE_REG01_DISP_ENABLE BIT(m_regs[1],6)
#define MEGADRIVE_REG0_DISPLAY_DISABLE BIT(m_regs[0],0)
#define MEGADRIVE_REG01_240_LINE BIT(m_regs[1],3)
#define MEGADRIVE_REG12_WINDOW_VPOS (m_regs[18]&31)
#define MEGADRIVE_REG12_WINDOW_DOWN BIT(m_regs[18],7)
#define MEGADRIVE_REG11_WINDOW_HPOS (m_regs[17]&31)
#define MEGADRIVE_REG11_WINDOW_RIGHT BIT(m_regs[17],7)
#define MEGADRIVE_REG04_PATTERN_ADDR_B (m_regs[4]&7)
#define MEGADRIVE_REG02_PATTERN_ADDR_A ((m_regs[2]&0x38)>>3)
#define MEGADRIVE_REG0B_HSCROLL_MODE (m_regs[11]&3)
#define MEGADRIVE_REG0B_VSCROLL_MODE BIT(m_regs[11],2)
#define MEGADRIVE_REG0D_HSCROLL_ADDR (m_regs[13]&63)
#define MEGADRIVE_REG0C_SHADOW_HIGLIGHT BIT(m_regs[12],3)
#define MEGADRIV_VDP_VRAM(v) m_vram[(v)&32767]
struct gfx_element{};
class sega315_5313_device{
public:
 u16 m_regs[64]{},m_vsram[64]{},m_vram[65536]{},m_sprite_renderline[1024]{},m_mdp_widescreen_sides[106]{};
 int m_imode=0,pad=53;
 struct nametable_t{u8 data[8];const u8 *addr;bool xflip;u16 colour,pri;};
 gfx_element *gfx(int){return nullptr;}
 int mdp_widescreen_padding()const{return pad;}
 u16 mdp_vram_word(u32 a)const{return m_vram[a&65535];}
 void mdp_render_widescreen_sides(int scanline);
 void get_vcolumn_tilebase(int &vc,int &tb,u16 base,int scroll,int line,int vs,int hs,int hc){vc=(scroll+line)&(vs*8-1);tb=((base>>1)+(vc>>3)*hs+hc)&32767;}
 void get_nametable(gfx_element*,u16 base,nametable_t &tile,int row){const u16 attr=m_vram[base];const int y=(row&7)^(attr&4096?7:0);for(int x=0;x<8;x++)tile.data[x]=(m_vram[(attr&2047)*16+y*2+x/4]>>(12-(x&3)*4))&15;tile.addr=tile.data;tile.colour=(attr>>13)&3;tile.pri=attr>>15;tile.xflip=attr&2048;}
 void fixed(unsigned a,u32 v){m_vram[a]=v>>16;m_vram[a+1]=v;}
};

PRODUCTION_FUNCTIONS

int main(){
 sega315_5313_device v;v.m_regs[1]=64;v.m_regs[4]=7;v.m_regs[16]=0x11;v.m_regs[17]=128;v.m_regs[33]=0xfc;
 for(int tile=1;tile<=15;tile++)for(int i=0;i<16;i++)v.m_vram[tile*16+i]=tile*0x1111;
 for(int y=0;y<64;y++)for(int x=0;x<64;x++)v.m_vram[0x7000+y*64+x]=1+(x+3*y)%15;
 for(int y=0;y<224;y++){unsigned e=0xe000+y*8;v.m_vram[e]=4096;v.fixed(e+4,0);v.fixed(e+6,y*4096);}
 for(int y: {0,8,223}){v.mdp_render_widescreen_sides(y);for(int i=0;i<106;i++){int x=i<53?i-53:320+i-53;int expected=1+(((x&511)>>3)+3*(y>>3))%15;assert(v.m_mdp_widescreen_sides[i] == (expected | 0x4000));}}

 // Affine mode: negative horizontal step and a per-line vertical delta.
 v.m_regs[33]=0xdc;v.m_vram[0xe000]=u16(-4096);v.m_vram[0xe001]=0;v.m_vram[0xe002]=0;v.m_vram[0xe003]=4096;v.fixed(0xe004,200*4096);v.fixed(0xe006,0);
 for(int y: {0,88,223}){v.mdp_render_widescreen_sides(y);for(int i=0;i<106;i++){int x=i<53?i-53:320+i-53;int expected=1+((((200-x)&511)>>3)+3*(y>>3))%15;assert(v.m_mdp_widescreen_sides[i]==(expected|0x4000));}}
 v.m_regs[33]=0x9c;
 for(int y: {0,88,223}){v.mdp_render_widescreen_sides(y);for(int i=0;i<106;i++){int x=i<53?i-53:320+i-53;int expected=1+((std::clamp(200-x,0,511)>>3)+3*(y>>3))%15;assert(v.m_mdp_widescreen_sides[i]==(expected|0x4000));}}
 // Standard plane B with fine horizontal scroll and full-screen vertical scroll.
 v.m_regs[33]=0;v.m_regs[13]=0x38;v.m_vram[0x7001]=13;v.m_vsram[1]=11;
 for(int y: {40,80,223}){v.mdp_render_widescreen_sides(y);for(int i=0;i<106;i++){int x=i<53?i-53:320+i-53;int expected=1+((((x-13)&511)>>3)+3*(((y+11)&511)>>3))%15;assert(v.m_mdp_widescreen_sides[i] == (expected | 0x4000));}}
 // Extra sprites compose at negative and newly exposed positive coordinates.
 v.m_sprite_renderline[-20+128]=0x85;v.m_sprite_renderline[350+128]=0x87;v.mdp_render_widescreen_sides(40);assert(v.m_mdp_widescreen_sides[33]==0x4005);assert(v.m_mdp_widescreen_sides[83]==0x4007);
 // Returning to the native mode must leave the unused presentation cache alone.
 std::fill_n(v.m_mdp_widescreen_sides,106,u16(0x1234));v.pad=0;v.mdp_render_widescreen_sides(40);for(u16 p:v.m_mdp_widescreen_sides)assert(p==0x1234);v.pad=53;
 // Disabled display must not retain the previous row's lateral picture.
 v.m_regs[1]=0;v.m_regs[7]=123;v.mdp_render_widescreen_sides(40);for(u16 p:v.m_mdp_widescreen_sides)assert(p==(123|0x4000));
 std::cout<<"sides: transformed, wrap, standard fine scrolling, sprite composition and display clearing passed\n";
}

"""


class MdpWidescreenTests(unittest.TestCase):
    def test_extra_world_pixels_follow_native_coordinates_and_composition(self):
        cpp = patched_fragments(PATCH.read_text(), "src/devices/video/315_5313.cpp")
        source = PROBE.replace("PRODUCTION_FUNCTIONS", "\n".join(
            full_function(cpp, signature) for signature in (
                "static u8 mdp_composite_pixel(",
                "void sega315_5313_device::mdp_render_widescreen_sides(",
            )))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "mdp_widescreen_probe.cpp"
            path.write_text(source, encoding="utf-8")
            probe = directory / ("mdp_widescreen_probe.exe" if os.name == "nt" else "mdp_widescreen_probe")
            subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
                "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                str(path), "-o", str(probe),
            ], check=True)
            result = subprocess.run([str(probe)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
