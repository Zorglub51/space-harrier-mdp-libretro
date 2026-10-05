"""Check the shipped direct register decoder against original M2 ARM execution."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_mdp_raster_cram import PATCH, patched_fragments, probe_source

ROOT = Path(__file__).resolve().parents[1]

class MdpRegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        text = probe_source(PATCH.read_text()).replace(
            "} else return 4;", "} else if (command == 'D') { for (unsigned i=0; i<64; ++i) if(vdp.m_regs[i]) std::cout << \"G \" << i << ' ' << vdp.m_regs[i] << '\\n'; } else return 4;")
        source = directory / 'probe.cpp'
        source.write_text(text)
        cls.probe = directory / ('probe.exe' if os.name == 'nt' else 'probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + ['-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(cls.probe)], check=True)

    def run_case(self, address, data, mask=0xffff):
        result = subprocess.run([str(self.probe)], input=f'W 9 {(address-0xc00000)//2} {data} {mask}\nD\nR 10\n', text=True, capture_output=True, check=True)
        return [tuple([s[0], *map(int, s[1:])]) for s in (line.split() for line in result.stdout.splitlines())]

    def compare(self, reference):
        self.assertEqual(reference['source']['binary_sha256'], '2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f')
        self.assertEqual(len(reference['cases']), 68)
        for case in reference['cases']:
            i, o = case['input'], case['output']
            with self.subTest(address=hex(i['byte_address']), data=i['data']):
                if o['direct_register']:
                    expected = [('G', v['index'], v['value']) for v in o['register_writes']]
                else:
                    expected = [('P', ((i['byte_address']-0xc00000)//2)&15, i['data'], 0xffff)]
                self.assertEqual(self.run_case(i['byte_address'], i['data']), expected)

    def test_all_registers_match_native_decoder(self):
        self.compare(json.loads((ROOT/'tests/fixtures/mdp_register_m2.json').read_text()))

    def test_fresh_original_execution_when_configured(self):
        path = os.environ.get('MDP_REGISTER_ORACLE_JSON')
        if not path: self.skipTest('MDP_REGISTER_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))

    def test_low_byte_lane_and_zero_write(self):
        # MAME's byte enables are an adapter rule, separate from the native
        # word-write oracle. The register physically stores only the low byte.
        self.assertEqual(self.run_case(0xc00148, 0x0091, 0x00ff), [('G', 36, 0x91)])
        self.assertEqual(self.run_case(0xc00148, 0x9100, 0xff00), [])
        self.assertEqual(self.run_case(0xc00148, 0), [])

    def test_register_storage_is_initialized_and_serialized(self):
        source = patched_fragments(PATCH.read_text(), 'src/devices/video/315_5313.cpp')
        self.assertIn('m_regs  = std::make_unique<u16[]>(64);', source)
        self.assertIn('memset(m_regs.get(), 0x00, 64 * sizeof(u16));', source)
        self.assertIn('save_pointer(NAME(m_regs), 64);', source)

if __name__ == '__main__': unittest.main()
