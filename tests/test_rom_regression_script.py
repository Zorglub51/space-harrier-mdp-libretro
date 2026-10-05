import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run-rom-regressions.sh"
RECORDER = """import json, os, sys
with open(os.environ["SH_MDP_INVOCATIONS"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
"""


class RomRegressionScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sh-mdp-script-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "build" / "mame").mkdir(parents=True)
        self.script = self.root / "scripts" / SCRIPT.name
        shutil.copyfile(SCRIPT, self.script)
        (self.root / "tests" / "libretro_regression.py").write_text(RECORDER)
        self.log = self.root / "invocations.jsonl"
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("SH_MDP_")}
        self.env.update(SH_MDP_ROM_DIR=str(self.root / "private roms"),
                        SH_MDP_INVOCATIONS=str(self.log))

    def core(self, name):
        path = self.root / "build" / "mame" / name
        path.touch()
        return str(path)

    def run_script(self, **environment):
        return subprocess.run(["bash", str(self.script)],
                              env={**self.env, **environment},
                              text=True, capture_output=True)

    def invocations(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def value(self, invocation, option):
        return invocation[invocation.index(option) + 1]

    def test_default_runs_both_games_and_prefers_shmdp_core(self):
        self.core("mame_libretro.so")
        expected_core = self.core("shmdp_libretro.so")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.invocations()
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(self.value(call, "--core") == expected_core for call in calls))
        self.assertEqual([Path(self.value(call, "--rom")).name for call in calls],
                         ["jp_jp_space_harrier.smp"] * 2 + ["jp_jp_Space_Harrier_II.smp"] * 2)
        for baseline, gameplay in zip(calls[::2], calls[1::2]):
            self.assertIn("--no-input", baseline)
            self.assertEqual(self.value(baseline, "--frames"), "1200")
            self.assertEqual(self.value(gameplay, "--frames"), "6000")
            self.assertEqual(self.value(gameplay, "--different-from"),
                             self.value(baseline, "--output"))

    def test_sh1_only_uses_dylib_and_keeps_report_names(self):
        self.core("shmdp_libretro.dylib")
        result = self.run_script(SH_MDP_GAME="sh1")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.invocations()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(Path(self.value(call, "--rom")).name == "jp_jp_space_harrier.smp"
                            for call in calls))
        self.assertEqual([Path(self.value(call, "--output")).name for call in calls],
                         ["space-harrier-no-input.json", "space-harrier.json"])

    def test_sh2_only_honours_explicit_core(self):
        self.core("shmdp_libretro.so")
        explicit_core = self.root / "custom core.dylib"
        explicit_core.touch()
        result = self.run_script(SH_MDP_GAME="sh2", SH_MDP_CORE=str(explicit_core))
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.invocations()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(self.value(call, "--core") == str(explicit_core) for call in calls))
        self.assertTrue(all(Path(self.value(call, "--rom")).name == "jp_jp_Space_Harrier_II.smp"
                            for call in calls))

    def test_legacy_core_remains_supported(self):
        expected_core = self.core("mame_libretro.dylib")
        result = self.run_script(SH_MDP_GAME="sh1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(self.value(call, "--core") == expected_core
                            for call in self.invocations()))

    def test_invalid_game_fails_before_running_frontend(self):
        self.core("shmdp_libretro.so")
        result = self.run_script(SH_MDP_GAME="sh3")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid SH_MDP_GAME", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_build_tree_reports_how_to_select_core(self):
        (self.root / "build" / "mame").rmdir()
        result = self.run_script(SH_MDP_GAME="sh1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set SH_MDP_CORE explicitly", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
