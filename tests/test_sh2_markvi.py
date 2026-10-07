"""Synthetic object-list tests: no private ROM, artwork or saved RAM."""
import ctypes as C
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def compile_probe(directory):
    library = Path(directory) / 'markvi.so'
    subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
        '-std=c++17', '-shared', '-fPIC', '-O2', '-I', str(ROOT/'src/markv'),
        str(ROOT/'tests/sh2_markvi_probe.cpp'), '-o', str(library)], check=True)
    f = C.CDLL(str(library)).markvi_build
    f.argtypes = [C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p, C.c_size_t]
    f.restype = C.c_size_t
    return f


def run_probe(f, rom, ram):
    rb, mb = C.create_string_buffer(bytes(rom)), C.create_string_buffer(bytes(ram))
    n = f(rb, len(rom), mb, None, 0)
    if n == C.c_size_t(-1).value:
        return None
    result = (C.c_ushort * (n * 5))()
    assert f(rb, len(rom), mb, result, n) == n
    return [tuple(result[i*5:i*5+5]) for i in range(n)]


class MarkVI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.probe = staticmethod(compile_probe(cls.temp.name))

    def setUp(self):
        self.rom, self.ram = bytearray(0x400000), bytearray(0x20000)
        self.put(0x13b78e, 0xff3542, 4)
        self.put(0xff38f2, 0xff5000, 4)
        self.put(0xff501c, 0x1000, 4)
        self.put(0xff502b, 4, 1)  # Body only.
        self.put(0x100a, 1, 1)
        self.put(0x100c, 0x2000, 4)
        self.put(0xff3542, 0x800 | 32)
        self.put(0x2001, 0x0f, 1)  # Four cells in each dimension.
        self.put(0x2002, 16)

    def put(self, address, value, size=2):
        mem = self.ram if address >= 0xfe0000 else self.rom
        offset = address - 0xfe0000 if address >= 0xfe0000 else address
        mem[offset:offset+size] = (value & ((1 << (size*8))-1)).to_bytes(size, 'big')

    def records(self):
        return run_probe(self.probe, self.rom, self.ram)

    def test_more_than_512_sprites_and_independent_zoom(self):
        # Six objects with 100 pieces each; no SAT-link truncation or quotas.
        self.put(0x100a, 100, 1)
        for i in range(100): self.put(0x2000+i*12+2, 1)
        for i in range(6):
            o = 0xff5000+i*0x4c
            self.put(o+0x18, o+0x4c if i<5 else 0, 4)
            self.put(o+0x1c, 0x1000, 4)
            self.put(o+0x2b, 4, 1)
            self.put(o+10, 1)
            self.put(o+0x40, 0x300+i*64)
        records = self.records()
        self.assertEqual(len(records), 600)
        self.assertEqual([records[i*100][4] for i in range(6)], [0x400+i*64 for i in range(6)])
        self.assertEqual(records[-1][2], 32+99)

    def test_more_than_128_independent_object_transforms(self):
        for i in range(200):
            o = 0xff5000+i*0x4c
            self.put(o+0x18, o+0x4c if i<199 else 0, 4)
            self.put(o+0x1c, 0x1000, 4)
            self.put(o+0x2b, 4, 1)
            self.put(o+10, 1)
            self.put(o+0x40, 512+i*64)
        records = self.records()
        self.assertEqual(len(records), 200)
        self.assertEqual([s[4] for s in records], [768+i*64 for i in range(200)])

    def test_negative_rounding_and_all_flip_coordinates(self):
        self.put(0xff500a, 1); self.put(0xff5040, 0x800)
        for offset,value in [(4,-3),(6,-5),(8,-13),(10,-17)]:self.put(0x2000+offset,value)
        for flags in range(4):
            self.put(0xff5028,flags,1)
            y,size,attr,x,zoom = self.records()[0]
            self.assertEqual((x,y), ((121 if flags&1 else 126),(119 if flags&2 else 125)))
            self.assertEqual((size,attr,zoom),(0x1f00,32+(flags<<11),0x900))

    def test_mirrored_halves_keep_palette_and_order(self):
        self.put(0xff5028,4,1);self.put(0xff5022,1,1)
        self.put(0x1006,8,1)
        a,b = self.records()
        self.assertEqual((a[3],b[3]),(160,96))
        self.assertEqual((a[2],b[2]),(0x2020,0x2820))

    def test_dead_hidden_cycle_and_empty_lists(self):
        self.put(0xff5020,0xfe,1);self.assertEqual(self.records(),[])
        self.put(0xff5020,0,1);self.put(0xff502b,0x84,1);self.assertEqual(self.records(),[])
        self.put(0xff5018,0xff5000,4);self.assertIsNone(self.records())
        self.put(0xff38f2,0,4);self.assertEqual(self.records(),[])

    def test_tile_cache_relocation_is_followed(self):
        self.put(0x13b78e,0xfe0100,4);self.put(0xfe0100,123)
        self.assertEqual(self.records()[0][2],123)


if __name__ == '__main__': unittest.main()
