"""Compare the complete production renderer with synthetic original M2 output.

Only register storage, unified VRAM reads and output storage are stubbed.
The fixture contains original execution results and no game ROM data.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, full_function, patched_fragments

FIXTURE = Path(__file__).resolve().parent / 'fixtures/mdp_sprite_list_m2.json'
BINARY_SHA256 = '2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f'


def probe_source():
    source = patched_fragments(PATCH.read_text(), 'src/devices/video/315_5313.cpp')
    method = full_function(source, 'void sega315_5313_device::mdp_render_spriteline(int scanline)')
    return r'''
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
using u8=std::uint8_t; using u16=std::uint16_t; using u32=std::uint32_t;
#define BIT(v,b) (((v)>>(b))&1U)
class sega315_5313_device {
public:
 int mdp_widescreen_padding() const {return 0;}
 u16 m_regs[64]{};
 std::array<u16,65536> vram{};
 std::unique_ptr<u16[]> m_sprite_renderline=std::make_unique<u16[]>(1024);
 u16 mdp_vram_word(u32 address) const {return vram[address&65535];}
 void mdp_render_spriteline(int scanline);
};
METHOD
int main(){
 int scanline,pattern,registers,writes;
 while(std::cin>>scanline>>pattern>>registers>>writes){
  sega315_5313_device vdp;
  for(int i=0;i<registers;++i){unsigned index,value;if(!(std::cin>>index>>value)||index>=64)return 2;vdp.m_regs[index]=u16(value);}
  if(pattern){
   // Exact input initialization documented by the native fixture.
   for(unsigned tile=0;tile<4096;++tile)for(unsigned row=0;row<8;++row){
    u32 pixels=0;
    for(unsigned x=0;x<8;++x)pixels=(pixels<<4)|(1+(tile+row*3+x*2+(tile>=2048?4:0))%15);
    vdp.vram[tile*16+row*2]=u16(pixels>>16);vdp.vram[tile*16+row*2+1]=u16(pixels);
   }
   unsigned sat=(vdp.m_regs[5]&127)<<8;
   std::fill_n(vdp.vram.begin()+sat,512,0);
   if(vdp.m_regs[36]&128){unsigned bank=(vdp.m_regs[36]&31)<<11;
    for(unsigned i=0;i<128;++i){vdp.vram[bank+i*8]=4096;vdp.vram[bank+i*8+3]=4096;}
   }
  }
  for(int i=0;i<writes;++i){unsigned address,value;if(!(std::cin>>address>>value)||address>=131072||(address&1))return 3;vdp.vram[address/2]=u16(value);}
  std::fill_n(vdp.m_sprite_renderline.get(),1024,0xffff);
  vdp.mdp_render_spriteline(scanline);
  for(int x=0;x<1024;++x)std::cout<<vdp.m_sprite_renderline[x]<<(x==1023?'\n':' ');
 }
 return std::cin.eof()?0:4;
}
'''.replace('METHOD', method)


def compile_probe(directory):
    source = directory / 'sprite-list-probe.cpp'
    source.write_text(probe_source())
    executable = directory / ('sprite-list-probe.exe' if os.name == 'nt' else 'sprite-list-probe')
    subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
        '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(executable),
    ], check=True)
    return executable


def run_cases(executable, cases):
    inputs = []
    for case in cases:
        registers = case['regs']
        writes = [(block[0] + 2 * offset, value)
                  for block in case['writes'] for offset, value in enumerate(block[1:])]
        inputs.append(f"{case['scanline']} {int(case.get('pattern', False))} {len(registers)} {len(writes)}")
        inputs.extend(f'{index} {value}' for index, value in registers.items())
        inputs.extend(f'{address} {value}' for address, value in writes)
    result = subprocess.run([str(executable)], input='\n'.join(inputs) + '\n',
                            text=True, capture_output=True, check=True, timeout=30)
    rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
    if len(rows) != len(cases) or any(len(row) != 1024 for row in rows):
        raise AssertionError('incomplete sprite output from compiled production method')
    return rows


def native_case(case):
    values = case['input']
    return {'scanline': values['scanline'], 'pattern': True,
            'regs': {1: 0x40, 5: values['reg5'], 12: values['reg12'], 36: values['reg36']},
            'writes': values['vram_writes']}


def native_pixels(row, width):
    # Convert legacy priority/bank packing to the native pre-composition buffer.
    return [(value & 0x3f) | ((value & 0x100) >> 2) | (0x8080 if value & 0x80 else 0)
            for value in row[128:128 + width]]


class MdpSpriteListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.probe = compile_probe(Path(cls.temporary.name))

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'], BINARY_SHA256)
        cases = fixture['cases']
        self.assertGreaterEqual(len(cases), 76)
        self.assertEqual(len({case['name'] for case in cases}), len(cases))
        outputs = run_cases(self.probe, [native_case(case) for case in cases])
        for case, output in zip(cases, outputs):
            with self.subTest(case=case['name']):
                width = case['input']['width']
                self.assertEqual(native_pixels(output, width), case['output']['pixels'])
                self.assertFalse(any(output[:128] + output[128 + width:]))

    def test_complete_renderer_matches_original_sprite_lists_and_pixels(self):
        self.compare(json.loads(FIXTURE.read_text()))

    def test_fresh_original_execution_when_configured(self):
        path = os.environ.get('MDP_SPRITE_LIST_ORACLE_JSON')
        if not path:
            self.skipTest('MDP_SPRITE_LIST_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))


if __name__ == '__main__':
    unittest.main()
