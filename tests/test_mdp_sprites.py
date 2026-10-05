"""Compare compiled sprite geometry from the shipped patch with M2 ARM samples.

Only zoom selection, vertical geometry, sample rows and the shrink lookup table
are covered here. Full SAT traversal, clipping and compositing remain separate
contracts; the fixture also retains original helper results for future work.
No game data or external MAME checkout is required.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/mdp_sprite_m2.json'


def probe_source(patch):
    source = patched_fragments(patch, 'src/devices/video/315_5313.cpp')
    def between(begin, end):
        start = source.index(begin)
        return source[start:source.index(end, start)]
    controls = between('const bool mdp_sprite_zoom', '/* Clear our Render Buffer */')
    zoom = between('u32 zoom_x =', 'if (m_imode == 3)')
    geometry = between('ypos = m_internal_sprite_attribute_table[spritenum * 4]', '\n\t\t\t}')
    sample = between('const int ystep =', 'const int xstep =')
    table = between('static constexpr u8 shrink_map', 'const int rowbytes =')
    return r'''
#include <algorithm>
#include <cstdint>
#include <iostream>
using u8=std::uint8_t; using u16=std::uint16_t; using u32=std::uint32_t;
#define BIT(v,b) (((v)>>(b))&1U)
#define MEGADRIV_VDP_VRAM(i) vram[(i)]
int main(){
 int scanline,sy,size,xword,zx,zy,attr,control;
 while(std::cin>>scanline>>sy>>size>>xword>>zx>>zy>>attr>>control){
  u16 vram[0x10000]{},m_regs[64]{},m_internal_sprite_attribute_table[4]{};
  const bool m_mdp_scaler=true; const int m_imode=0,spritenum=0,base_address=0xe000;
  m_regs[36]=control;vram[(base_address/2)+3]=u16(xword);m_internal_sprite_attribute_table[0]=u16(sy);
  // Synthetic data is installed in both known game banks; control still
  // determines which pointer the compiled production expression computes.
  for(int base: {0,0x11000,0x1f000}){unsigned at=(base/2+((xword>>9)&127)*8)&65535;vram[at]=u16(zx);vram[(at+3)&65535]=u16(zy);}
  auto mdp_vram_word=[&](unsigned a){return vram[a&65535];};
  int ypos=0,drawypos=0,drawheight=0; const int height=((size>>8)&3)+1;
  const bool yflip=bool(attr&0x1000);
  CONTROLS
  ZOOM
  GEOMETRY
  // Existing MAME line-intersection predicate; the changed producer above
  // supplies its circular row and unforced height.
  const bool accepted=(drawypos<=scanline)&&(drawypos+drawheight>scanline);
  int sampled=-1;
  if(accepted){ SAMPLE sampled=ysrc; }
  std::cout<<mdp_sprite_zoom<<' '<<mdp_zoom_base*2<<' '<<scanline-drawypos<<' '<<drawheight<<' '<<accepted<<' '<<sampled<<' '<<(zoom_x>>6)<<'\n';
 }
 TABLE
 for(int span=0;span<8;++span){std::cout<<"T "<<span;for(int i=0;i<span;++i)std::cout<<' '<<int(shrink_map[span][i]);std::cout<<'\n';}
}
'''.replace('CONTROLS', controls).replace('ZOOM', zoom).replace('GEOMETRY', geometry).replace('SAMPLE', sample).replace('TABLE', table)


def clipping_probe_source(patch):
    source = patched_fragments(patch, 'src/devices/video/315_5313.cpp')
    start = source.index('const int span = end - start;')
    guard = source[start:source.index('const u32 tile =', start)]
    start = source.index('static constexpr u8 shrink_map')
    table = source[start:source.index('const int rowbytes =', start)]
    start = source.index('int sx = (span == 8)')
    sample = source[start:source.index(';', start)+1]
    # Rendering into the 512-pixel sprite buffer and then cropping is represented
    # by the final viewport check. The modified guard and lookup are production
    # statements, not a second implementation of their decision.
    return r"""
#include <cstdint>
#include <iostream>
using u8=std::uint8_t;
int main(){
 TABLE
 int start,width;
 while(std::cin>>start>>width){
  int pixels[16]{},end=start+width;
  do {
   GUARD
   for(int out=0;out<span;++out){
    SAMPLE
    if(start+out>=0 && start+out<16)pixels[start+out]=sx+1;
   }
  }while(false);
  for(int x=0;x<16;++x)std::cout<<pixels[x]<<(x==15?'\n':' ');
 }
}
""".replace('TABLE',table).replace('GUARD',guard).replace('SAMPLE',sample)


class MdpSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory/'probe.cpp'
        source.write_text(probe_source(PATCH.read_text()))
        cls.probe = directory/('probe.exe' if os.name=='nt' else 'probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++'))+['-std=c++17','-Wall','-Wextra','-Werror',str(source),'-o',str(cls.probe)], check=True)
        clip_source = directory/'clip.cpp'
        clip_source.write_text(clipping_probe_source(PATCH.read_text()))
        cls.clip_probe = directory/('clip.exe' if os.name=='nt' else 'clip')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++'))+['-std=c++17','-Wall','-Wextra','-Werror',str(clip_source),'-o',str(cls.clip_probe)], check=True)

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'], '2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f')
        geometry = [c for c in fixture['cases'] if c['kind']=='geometry']
        banks = [c for c in fixture['cases'] if c['kind']=='bank']
        self.assertEqual(len(geometry), 9)
        self.assertEqual(len(banks), 6)
        inputs = []
        for c in geometry:
            i=c['input']; inputs.append(' '.join(map(str,[i['scan'],i['sat_y'],i['size'],i['xword'],i['zx'],i['zy'],i['attr'],0x91])))
        for c in banks: inputs.append(f"0 128 0 128 4096 4096 1 {c['control']}")
        out=subprocess.run([str(self.probe)],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True).stdout.splitlines()
        for c,line in zip(geometry,out):
            i,o=c['input'],c['output'];v=list(map(int,line.split()))
            with self.subTest(case=c['name']):
                self.assertEqual(v[2:5],[o['delta_mod1024'],o['height'],int(o['accepted'])])
                if o['accepted']:
                    source=o['source_y'];height=((i['size']>>8)&3)+1
                    if i['attr']&0x1000: source=height*8-1-source
                    self.assertEqual(v[5],source)
                    self.assertEqual(v[6],o['x_step'])
        for c,line in zip(banks,out[len(geometry):]):
            v=list(map(int,line.split()))
            with self.subTest(case=c['name']):
                self.assertEqual(v[0],int(c['enabled']))
                if c['enabled']: self.assertEqual(v[1],c['base_bytes'])
        tables={int(s[1]):list(map(int,s[2:])) for s in map(str.split,out) if s[0]=='T'}
        for c in fixture['cases']:
            if c['kind']=='shrink' and c['name'].startswith('span_') and c['span']<8:
                span=c['span'];self.assertEqual(tables[span],[v-1 for v in c['pixels'][2:2+span]])

    def test_reduced_cell_clipping_matches_native_arm(self):
        cases=[c for c in json.loads(FIXTURE.read_text())['cases'] if c['kind']=='shrink']
        inputs=''.join(f"{c['x']} {c['span']}\n" for c in cases)
        result=subprocess.run([str(self.clip_probe)],input=inputs,text=True,capture_output=True,check=True)
        rows=[list(map(int,line.split())) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows),len(cases))
        for case,row in zip(cases,rows):
            with self.subTest(case=case['name']):
                self.assertEqual(row,[v&15 for v in case['pixels']])

    def test_geometry_and_zoom_bank_match_native_arm(self):
        self.compare(json.loads(FIXTURE.read_text()))

    def test_fresh_original_execution_when_configured(self):
        path=os.environ.get('MDP_SPRITE_ORACLE_JSON')
        if not path: self.skipTest('MDP_SPRITE_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))

if __name__=='__main__': unittest.main()
