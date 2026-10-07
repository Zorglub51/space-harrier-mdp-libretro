"""Check native Deflicker byte lanes and independently verified ROM consumers."""
import ctypes
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeflickerOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        p = Path(cls.temp.name)
        (p/'probe.cpp').write_text('''
#include "sh_deflicker_options.h"
extern "C" int parse(const char *s) { return sh_mdp_deflicker::parse(s); }
extern "C" unsigned read(unsigned data, unsigned mask, int mode) {
 return sh_mdp_deflicker::read(data, mask, mode);
}
''')
        compiler=shlex.split(os.environ.get('CXX','c++'))
        subprocess.run(compiler+['-std=c++17','-shared','-fPIC','-I',str(ROOT/'src/markv'),str(p/'probe.cpp'),'-o',str(p/'probe.so')],check=True,capture_output=True)
        cls.lib=ctypes.CDLL(str(p/'probe.so'))
        cls.lib.parse.argtypes=[ctypes.c_char_p]
        cls.lib.read.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unknown_and_missing_leave_game_in_control(self):
        for value in (None,b'',b'game',b'invalid',b'ON1'):
            self.assertEqual(self.lib.parse(value),-1)
        for value,mode in ((b'off',0),(b'on1',1),(b'on2',2)):
            self.assertEqual(self.lib.parse(value),mode)

    def test_preserves_neighbor_and_respects_byte_mask(self):
        for mode in (-1,0,1,2,3):
            for data in (0,0x00ff,0x010a,0x02fe,0xa55a,0xffff):
                for mask in (0,0xff,0xff00,0xffff,0xf000,0x0f00):
                    result=self.lib.read(data,mask,mode)
                    self.assertEqual(result & 0xff,data & 0xff)
                    expected=data
                    if mode in (0,1,2):
                        effective=mask & 0xff00
                        expected=(data & ~effective)|((mode<<8)&effective)
                    self.assertEqual(result,expected)

    def test_private_rom_consumers_and_menu_values(self):
        directory=os.environ.get('SH_MDP_ROM_DIR')
        if not directory:self.skipTest('SH_MDP_ROM_DIR not supplied')
        cases=[('jp_jp_space_harrier.smp','e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72',0xff3c36,[0x170366,0x17048c,0x1707a2]),
               ('jp_jp_Space_Harrier_II.smp','80f576af01d6413c0b92073e2f947b0431f12a74',0xff2e62,[0x13b07a,0x13b1a0,0x13b4b4])]
        for filename,sha,address,sites in cases:
            data=(Path(directory)/filename).read_bytes()
            self.assertEqual(hashlib.sha1(data).hexdigest(),sha)
            for site in sites:
                # Original opcode words can be M2 hook sentinels; operands remain intact.
                self.assertEqual(data[site+2:site+6],address.to_bytes(4,'big'))
            for text in (b'DEFLICKER',b'ON1',b'ON2'):
                self.assertIn(text,data)


if __name__=='__main__':unittest.main()
