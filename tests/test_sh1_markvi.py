"""SH1 emitter arithmetic and capacity tests, using synthetic ROM/RAM only."""
import ctypes as C
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_sh2_markvi import run_probe

ROOT = Path(__file__).resolve().parents[1]


def compile_probe(directory):
    library = Path(directory) / 'sh1-markvi.so'
    subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
        '-std=c++17', '-shared', '-fPIC', '-O2', '-I', str(ROOT/'src/markv'),
        str(ROOT/'tests/sh1_markvi_probe.cpp'), '-o', str(library)], check=True)
    probe = C.CDLL(str(library)).sh1_markvi_build
    probe.argtypes = [C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p, C.c_size_t]
    probe.restype = C.c_size_t
    wide = C.CDLL(str(library)).sh1_markvi_build_wide
    wide.argtypes, wide.restype = probe.argtypes, probe.restype
    return probe, wide


class SH1MarkVI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        normal, wide = compile_probe(cls.temp.name)
        cls.probe, cls.wide_probe = staticmethod(normal), staticmethod(wide)

    def setUp(self):
        self.rom, self.ram = bytearray(0x400000), bytearray(0x20000)
        self.put(0xff40b8, 0xff5000, 4)
        self.object(0xff5000)
        self.put(0x100a, 1, 1)
        self.put(0x100c, 0x2000, 4)
        self.put(0xff3d16, 0x800 | 32)
        self.put(0x2001, 0x0f, 1)
        self.put(0x2002, 16)

    def put(self, address, value, size=2):
        mem = self.ram if address >= 0xfe0000 else self.rom
        offset = address - 0xfe0000 if address >= 0xfe0000 else address
        mem[offset:offset+size] = (value & ((1 << (size*8))-1)).to_bytes(size, 'big')

    def object(self, address, next_object=0):
        self.put(address+0x18, next_object, 4)
        self.put(address+0x1c, 0x1000, 4)
        self.put(address+0x2b, 4, 1)  # No shadow for the basic body fixture.

    def records(self, wide=False):
        return run_probe(self.wide_probe if wide else self.probe, self.rom, self.ram)

    def test_measured_native_constructor_vectors(self):
        fixture = json.loads((ROOT/'tests/fixtures/sh1_markvi_emitter_native.json').read_text())
        self.put(0xff501c, 0xfe1000, 4)
        self.put(0xff500c, 160); self.put(0xff500e, -7)
        self.put(0xff5022, 2, 1); self.put(0xff5040, 0x875)
        self.put(0xfe1006, 8, 1); self.put(0xfe100a, 2, 1)
        self.put(0xfe100c, 0xfe2000, 4); self.put(0xff3d16, 0x8055)
        for offset, value, size in [(1,15,1),(2,16,2),(4,-13,2),(6,-17,2),
                                    (8,-35,2),(10,-39,2),(13,5,1),(14,4,2),
                                    (16,7,2),(18,11,2),(20,-31,2),(22,-35,2)]:
            self.put(0xfe2000+offset, value, size)
        self.assertEqual(len(fixture['cases']), 96)
        for case in fixture['cases']:
            with self.subTest(case=case['case']):
                self.put(0xff1be0, case['bank'])
                self.put(0xff3c36, case['deflicker'], 1)
                self.put(0xff5028, case['flags']|0x10, 1)
                self.put(0xff500a, 500 if case['scale'] else 0)
                # Native physical SAT partitions may reorder screen regions.
                self.assertCountEqual(self.records(), [tuple(s) for s in case['records']])

    def test_more_than_512_pieces_without_sat_or_partition_quotas(self):
        self.put(0x100a, 100, 1)
        for i in range(100): self.put(0x2000+i*12+2, 1)
        for i in range(6):
            o = 0xff5000+i*0x4c
            self.object(o, o+0x4c if i<5 else 0)
            self.put(o+10, 1)
            self.put(o+0x40, 0x300+i*64)
        records = self.records()
        self.assertEqual(len(records), 600)
        self.assertEqual([records[i*100][4] for i in range(6)], [0x400+i*64 for i in range(6)])
        self.assertEqual(records[-1][2], 32+99)

    def test_more_than_128_independent_transforms(self):
        for i in range(200):
            o = 0xff5000+i*0x4c
            self.object(o, o+0x4c if i<199 else 0)
            self.put(o+10, 1)
            self.put(o+0x40, 512+i*64)
        records = self.records()
        self.assertEqual(len(records), 200)
        self.assertEqual([s[4] for s in records], [768+i*64 for i in range(200)])

    def test_native_flip_coordinates_signed_fractional_rounding(self):
        self.put(0xff500a, 1); self.put(0xff5040, 0x800)
        for offset, value in [(4,-3),(6,-5),(8,-13),(10,-17)]:
            self.put(0x2000+offset, value)
        for flags in range(4):
            self.put(0xff5028, flags, 1)
            y, size, attr, x, zoom = self.records()[0]
            self.assertEqual((x,y), ((121 if flags&1 else 126),(119 if flags&2 else 125)))
            self.assertEqual((size,attr,zoom), (0x1f00,32+(flags<<11),0x900))

    def test_mirrored_halves_native_attribute_masks_and_order(self):
        self.put(0x1006, 8, 1); self.put(0xff5022, 1, 1)
        for flags in range(4,8):
            self.put(0xff5028, flags|0x10, 1)
            first, second = self.records()
            self.assertEqual((first[3],second[3]), (160,96))
            self.assertEqual((first[2],second[2]), (0xa020,0x2820+(0x1000 if flags&2 else 0)))

    def test_scaled_later_rows_reuse_native_first_row_x_positions(self):
        self.put(0xff500a, 1); self.put(0xff5040, 0x875)
        self.put(0x100a, 2, 1)
        self.put(0x2004, -13); self.put(0x2006, -17)
        self.put(0x2010, 7); self.put(0x2012, 11)
        records = self.records()
        self.assertEqual([s[3] for s in records], [121,121])
        self.assertEqual([s[0] for s in records], [119,133])
        self.put(0xff500a, 0)
        self.assertEqual([s[3] for s in self.records()], [115,135])

    def test_all_bodies_precede_shadows_and_sh1_ground_projection(self):
        self.object(0xff5000, 0xff504c); self.object(0xff504c)
        self.put(0xff502b, 0, 1); self.put(0xff5060, 0)
        # Native SH1 fixed-size shadow descriptor is 1304, not SH2's 072E.
        self.put(0x130c, 1); self.put(0x130e, 1, 1); self.put(0x1310, 0x3000, 4)
        self.put(0xff3d18, 0x123); self.put(0x3001, 3, 1)
        self.put(0x3004, 4); self.put(0x3006, -8)
        self.put(0x3c63e2, 0x4000)
        self.put(0xff40a2, 400); self.put(0xff40a4, 120)
        self.put(0xff500e, 77)  # Body height does not move the shadow.
        records = self.records()
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0][0], 205)
        self.assertEqual(records[1][2], 32)
        self.assertEqual(records[2], (340,0x0300,0x6123,132,0x1000))

    def test_scaled_shadow_uses_sh1_lod_reciprocal_and_ground_tables(self):
        self.put(0xff502b, 0, 1); self.put(0xff500a, 0x400)
        self.put(0xff5040, 0x800)
        self.put(0x12f9, 2, 1); self.put(0x130a, 8, 1)
        self.put(0x130c, 1); self.put(0x130e, 1, 1); self.put(0x1310, 0x3000, 4)
        self.put(0xff3d18, 0x123); self.put(0x3001, 3, 1)
        self.put(0x3004, 4); self.put(0x3006, -8)
        self.put(0x3c63e2+128, 0x4000)
        self.put(0x3c7104+32, 0x400)
        self.put(0x3c6904+231*2, 0x1000)
        self.put(0xff40a2, 400); self.put(0xff40a4, 120)
        self.assertEqual(self.records()[1], (346,0x0300,0x6123,129,0x500))

    def test_sh1_hidden_bit_hides_both_body_and_shadow(self):
        self.put(0xff502b, 0x80, 1)
        self.assertEqual(self.records(), [])
        self.put(0xff502b, 0, 1); self.put(0xff5020, 0xfe, 1)
        self.assertEqual(self.records(), [])

    def test_thinned_body_and_shadow_reappear_but_independent_hides_remain(self):
        self.put(0x130c, 1); self.put(0x130e, 1, 1); self.put(0x1310, 0x3000, 4)
        self.put(0xff3d18, 0x123); self.put(0x3001, 3, 1)
        self.put(0xff40a4, 100)
        for routine in (0x1246c8,0x1247f0,0x124ae4,0x124e20,0x12510e,0x1e41d8):
            self.put(0xff5010, routine, 4); self.put(0xff502b, 0x80, 1)
            self.assertEqual(len(self.records()), 2)
            self.assertEqual(self.records()[0][2], 32)
            self.assertEqual(self.records()[1], (228,0x0300,0x6123,128,0x1000))
            self.put(0xff502b, 0x84, 1)
            self.assertEqual(len(self.records()), 1)  # Bit04 still hides the shadow.
        # Harrier invulnerability, other routines and inactive poses stay native.
        self.put(0xff502b, 0x80, 1)
        for routine in (0x1ddf52,0x0c8560,0):
            self.put(0xff5010, routine, 4)
            self.assertEqual(self.records(), [])
        self.put(0xff5010, 0x1246c8, 4)
        for pose in (0xfe,0xff):
            self.put(0xff5020, pose, 1)
            self.assertEqual(self.records(), [])

    def test_wider_viewport_keeps_additional_edge_pieces(self):
        self.put(0xff500c, -80)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.records(True)[0][3], 48)
        self.put(0xff500c, 360)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.records(True)[0][3], 488)

    def test_invalid_object_chains_fail_without_hanging(self):
        for next_object in (0xff5000, 0xff5001, 0xfe5000, 0xffffb6):
            self.put(0xff5018, next_object, 4)
            self.assertIsNone(self.records())
        self.put(0xff40b8, 0, 4)
        self.assertEqual(self.records(), [])


if __name__ == '__main__': unittest.main()
