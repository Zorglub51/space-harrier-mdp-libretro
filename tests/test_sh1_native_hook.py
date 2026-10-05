"""Compare the portable block against outputs of the original M2 ARM code.

The committed fixture contains synthetic inputs and measured register outputs,
not executable M2 code or game data. SH1_ORACLE_JSON can select a fresh oracle run.
"""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sh1_collision_m2.json"


class Sh1NativeHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.probe = Path(cls.temp.name) / ("sh1_hook_probe.exe" if os.name == "nt" else "sh1_hook_probe")
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        subprocess.run(
            compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                        str(ROOT / "tests" / "sh1_hook_probe.cpp"), "-o", str(cls.probe)],
            check=True,
        )

    def compare_reference(self, reference):
        self.assertEqual(reference["schema"], 1)
        self.assertTrue(reference["cases"], "an empty oracle run proves nothing")
        for case in reference["cases"]:
            with self.subTest(case=case["name"]):
                inputs = case["input"]
                words = inputs["memory_words"]
                values = [inputs[key] for key in (
                    "d1", "d4", "d6", "a0", "a2", "a4", "flags", "x", "ticks")]
                values.append(len(words))
                for word in words:
                    values.extend((word["address"], word["value"]))
                result = subprocess.run(
                    [str(self.probe)], input=" ".join(map(str, values)) + "\n",
                    capture_output=True, text=True, check=True,
                )
                actual = json.loads(result.stdout)
                # All oracle outputs are checked, including upper register words,
                # X, dispatch counter wraparound and the next guest PC.
                self.assertEqual({key: actual[key] for key in case["output"]}, case["output"])
                self.assertTrue(actual["unrelated_registers_preserved"])
                self.assertEqual(actual["reads"], [
                    (inputs["a2"] + 10) & 0xFFFFFE,
                    (inputs["a4"] + 10) & 0xFFFFFE,
                ])

    def test_matches_original_arm_reference(self):
        self.compare_reference(json.loads(FIXTURE.read_text(encoding="utf-8")))

    def test_matches_fresh_original_arm_run_when_configured(self):
        path = os.environ.get("SH1_ORACLE_JSON")
        if not path:
            self.skipTest("SH1_ORACLE_JSON is not configured")
        self.compare_reference(json.loads(Path(path).read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
