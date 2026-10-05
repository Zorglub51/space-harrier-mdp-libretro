"""Compare the SH2 line-phase reference with measured original ARM outputs.

Fixtures contain synthetic state, not private ROM or executable emulator bytes.
The actual core runs reconstructed 68000 code; this portable block is a reference.
"""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sh2_line_phase_m2.json"


class Sh2NativeHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.probe = Path(cls.temp.name) / ("sh2_hook_probe.exe" if os.name == "nt" else "sh2_hook_probe")
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        subprocess.run(
            compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                        str(ROOT / "tests" / "sh2_hook_probe.cpp"), "-o", str(cls.probe)],
            check=True,
        )

    def compare_reference(self, reference):
        self.assertEqual(reference["schema"], 1)
        self.assertTrue(reference["cases"], "an empty oracle run proves nothing")
        self.assertEqual(reference["source"]["guest_hook_pc"], 0x18BCF4)
        for case in reference["cases"]:
            with self.subTest(case=case["name"]):
                inputs = case["input"]
                values = [inputs[key] for key in (
                    "d0", "d1", "d4", "a0", "limit_ff116a", "flags", "x", "ticks")]
                result = subprocess.run(
                    [str(self.probe)], input=" ".join(map(str, values)) + "\n",
                    capture_output=True, text=True, check=True,
                )
                actual = json.loads(result.stdout)
                self.assertEqual({key: actual[key] for key in case["output"]}, case["output"])
                self.assertTrue(actual["unrelated_registers_preserved"])

    def test_matches_original_arm_reference(self):
        self.compare_reference(json.loads(FIXTURE.read_text(encoding="utf-8")))

    def test_matches_fresh_original_arm_run_when_configured(self):
        path = os.environ.get("SH2_ORACLE_JSON")
        if not path:
            self.skipTest("SH2_ORACLE_JSON is not configured")
        self.compare_reference(json.loads(Path(path).read_text(encoding="utf-8")))

    def test_rom_reconstruction_copies_the_full_register(self):
        spec = importlib.util.spec_from_file_location("sh2_rompatch", ROOT / "rompatch" / "patch.py")
        patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patch)
        entries = [entry for entry in patch.SH2 if entry[0] == 0x18BCF4]
        self.assertEqual([(entry[1], entry[2]) for entry in entries], [(0x4E75, 0x2204)])
        # Native samples distinguish MOVE.L from the former NOP and MOVE.W.
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertTrue(any(case["input"]["d1"] != case["output"]["d1"] for case in cases))
        self.assertTrue(any((case["input"]["d1"] ^ case["output"]["d1"]) & 0xFFFF0000
                            for case in cases))


if __name__ == "__main__":
    unittest.main()
