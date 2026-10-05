"""Exercise the complete renderer with the earlier native geometry fixtures.

This compiles the production MDP method, not obsolete fallback fragments.
Native helper observations determine sampled rows and clipped pixels.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from test_mdp_sprite_list import BINARY_SHA256, compile_probe, run_cases

FIXTURE = Path(__file__).resolve().parent / 'fixtures/mdp_sprite_m2.json'


def single_sprite(scanline, y, size, xword, attr, zx, zy, control=0x91, pattern=True):
    entry = (control & 31) * 0x1000 + ((xword >> 9) & 127) * 16
    return {'scanline': scanline, 'pattern': pattern,
            'regs': {1: 0x40, 5: 0x70, 12: 0x81, 36: control},
            'writes': [[0xe000, y, size, attr, xword], [entry, zx, 0, 0, zy]]}


class MdpSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.probe = compile_probe(Path(cls.temporary.name))

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'], BINARY_SHA256)
        geometry = [case for case in fixture['cases'] if case['kind'] == 'geometry']
        shrink = {case['span']: [p - 1 for p in case['pixels'][2:2 + case['span']]]
                  for case in fixture['cases'] if case['kind'] == 'shrink'
                  and case['name'].startswith('span_')}
        self.assertEqual(len(geometry), 9)
        inputs = [single_sprite(i['scan'], i['sat_y'], i['size'], i['xword'],
                                i['attr'], i['zx'], i['zy'])
                  for i in (case['input'] for case in geometry)]
        for case, row in zip(geometry, run_cases(self.probe, inputs)):
            expected = [0] * 320
            observed = case['output']
            if observed['accepted']:
                span = observed['x_step'] // 8
                attr = observed['tile_attr']
                tile = attr & 0x7ff
                source_row = observed['source_row']
                if attr & 0x1000:
                    source_row = 7 - source_row
                for x, source_x in enumerate(shrink[span]):
                    if attr & 0x800:
                        source_x = 7 - source_x
                    expected[x] = 1 + (tile + source_row * 3 + source_x * 2) % 15
            with self.subTest(case=case['name']):
                self.assertEqual([value & 15 for value in row[128:448]], expected)

    def test_geometry_matches_native_sampled_rows(self):
        self.compare(json.loads(FIXTURE.read_text()))

    def test_reduced_cells_and_clipping_match_native_arm(self):
        cases = [case for case in json.loads(FIXTURE.read_text())['cases']
                 if case['kind'] == 'shrink']
        inputs = []
        for case in cases:
            sprite = single_sprite(0, 128, 0, (case['x'] + 128) & 511,
                                   1 | case['attr'], case['span'] * 512, 4096, pattern=False)
            sprite['writes'].append([32] + [0x1234, 0x5678] * 8)
            inputs.append(sprite)
        for case, row in zip(cases, run_cases(self.probe, inputs)):
            with self.subTest(case=case['name']):
                self.assertEqual([value & 15 for value in row[128:144]],
                                 [value & 15 for value in case['pixels']])

    def test_zoom_bank_selection_changes_the_rendered_width(self):
        cases = [case for case in json.loads(FIXTURE.read_text())['cases'] if case['kind'] == 'bank']
        spans = {0: 4, 0x11000: 3, 0x1f000: 2}
        inputs = []
        for case in cases:
            # Keep graphics outside the transform table when bank zero is used.
            sprite = single_sprite(0, 128, 0, 128, 0x100, 4096, 4096, case['control'])
            sprite['writes'].extend([base, span * 512, 0, 0, 4096] for base, span in spans.items())
            inputs.append(sprite)
        for case, row in zip(cases, run_cases(self.probe, inputs)):
            expected_width = spans[case['base_bytes']] if case['enabled'] else 8
            with self.subTest(case=case['name']):
                self.assertEqual([x for x, value in enumerate(row[128:448]) if value],
                                 list(range(expected_width)))

    def test_fresh_original_execution_when_configured(self):
        path = os.environ.get('MDP_SPRITE_ORACLE_JSON')
        if not path:
            self.skipTest('MDP_SPRITE_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))


if __name__ == '__main__':
    unittest.main()
