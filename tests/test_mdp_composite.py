"""Execute the shipped compositor against synthetic original ARM observations.

The actual helper is extracted from the public patch and compiled unchanged.
No ROM or renderer model is required. These cases cover native indexed
composition; converting indices into frontend RGB is a separate contract.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, full_function

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/mdp_composite_m2.json'


class MdpCompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = directory/'probe.cpp'
        body = full_function(patched_fragments(PATCH.read_text(), 'src/devices/video/315_5313.cpp'),
                             'static u8 mdp_composite_pixel(')
        source.write_text('''#include <cstdint>
#include <iostream>
using u8=std::uint8_t; using u16=std::uint16_t;
'''+body+'''
int main(){unsigned plane,sprite,shadow;
 while(std::cin>>plane>>sprite>>shadow)
  std::cout<<unsigned(mdp_composite_pixel(u16(plane),u16(sprite),shadow!=0))<<'\\n';
 return std::cin.eof()?0:1;
}
''')
        cls.probe = directory/('probe.exe' if os.name=='nt' else 'probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++'))+
                       ['-std=c++17','-Wall','-Wextra','-Werror',str(source),'-o',str(cls.probe)], check=True)

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'],
                         '2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f')
        self.assertEqual(fixture['entry'], 0xc2472)
        self.assertEqual(fixture['stop_before'], 0xc1e5c)
        self.assertEqual(len(fixture['cases']), 208)
        inputs=[]
        for c in fixture['cases']:
            i=c['input'];inputs.append(f"{i['plane']} {i['sprite']} {int(i['shadow_enabled'])}")
        result=subprocess.run([str(self.probe)],input='\n'.join(inputs)+'\n',
                              text=True,capture_output=True,check=True)
        output=list(map(int,result.stdout.splitlines()))
        self.assertEqual(len(output),len(fixture['cases']))
        for case,actual in zip(fixture['cases'],output):
            with self.subTest(**case['input']):
                self.assertEqual(actual,case['output_index'])

    def test_priority_palette_and_shadow_match_native_arm(self):
        self.compare(json.loads(FIXTURE.read_text()))

    def test_fresh_original_execution_when_configured(self):
        path=os.environ.get('MDP_COMPOSITE_ORACLE_JSON')
        if not path:self.skipTest('MDP_COMPOSITE_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))

if __name__=='__main__':unittest.main()
