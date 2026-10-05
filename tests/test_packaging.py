"""Verify actual 7z extraction, download limits, and complete source selection."""

import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    import package_archive
    import package_source
finally:
    sys.path.pop(0)


@unittest.skipUnless(shutil.which("7zz") or shutil.which("7z"), "7-Zip is not installed")
class ArchiveTests(unittest.TestCase):
    def round_trip(self, byte_count, expected_volumes, download_limit=10_000_000):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            package = temp / "package with spaces"
            package.mkdir()
            original = random.Random(42).randbytes(byte_count)
            (package / "payload.dat").write_bytes(original)
            (package / "BUILD.json").write_text(json.dumps({"package_version": "test"}))
            if os.name != "nt":
                (package / "tool-link").symlink_to("not-built-yet")
            archive = temp / "downloads" / "test.7z"
            delivered = package_archive.package_archive(package, archive, download_limit)
            volumes = [path for path in delivered if path.name == "test.7z"
                       or path.suffix[1:].isdigit()]
            self.assertEqual(len(volumes), expected_volumes)
            if download_limit:
                for path in delivered:
                    self.assertLess(path.stat().st_size, download_limit)
            if expected_volumes > 1:
                self.assertTrue(all(path.stat().st_size <= 9_500_000 for path in volumes))
                self.assertEqual(volumes[0].name, "test.7z.001")
            else:
                self.assertEqual(volumes[0].name, "test.7z")
            metadata = json.loads((archive.parent / "test.7z.BUILD.json").read_text())
            self.assertEqual(metadata["archive_format"], "7z")
            self.assertEqual(metadata["split"], expected_volumes > 1)
            self.assertEqual(metadata["archive_files"], [
                {"name": path.name, "size_bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in volumes
            ])
            sums = (archive.parent / "test.7z.SHA256SUMS").read_text().splitlines()
            self.assertEqual(len(sums), len(delivered) - 1)
            for line in sums:
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((archive.parent / name).read_bytes()).hexdigest(), expected)
            extracted = temp / "extracted"
            seven_zip = shutil.which("7zz") or shutil.which("7z")
            subprocess.run([seven_zip, "x", str(volumes[0]), f"-o{extracted}", "-y"],
                           check=True, stdout=subprocess.DEVNULL)
            restored = extracted / package.name
            self.assertEqual((restored / "payload.dat").read_bytes(), original)
            if os.name != "nt":
                self.assertTrue((restored / "tool-link").is_symlink())
                self.assertEqual(os.readlink(restored / "tool-link"), "not-built-yet")
            for line in (restored / "FILES_SHA256SUMS").read_text().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((restored / name).read_bytes()).hexdigest(), expected)

    def test_small_package_is_one_normal_archive(self):
        self.round_trip(1024, 1)

    def test_package_between_volume_and_download_limits_is_joined(self):
        self.round_trip(9_600_000, 1)

    def test_large_package_uses_extractable_capped_volumes(self):
        self.round_trip(10_100_000, 2)

    def test_release_archive_has_no_automatic_size_limit(self):
        self.round_trip(10_100_000, 1, download_limit=0)


class SourceSelectionTests(unittest.TestCase):
    def test_tracked_upstream_sources_survive_broad_ignore_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            checkout, copied = temp / "checkout", temp / "copied"
            checkout.mkdir()
            subprocess.run(["git", "init", "-q", str(checkout)], check=True)
            contents = {
                ".gitignore": "/*\n!/src/\n",
                "3rdparty/dependency.c": "tracked dependency\n",
                "Makefile.libretro": "tracked build instructions\n",
                "src/code.cpp": "modified source\n",
                "build/compiler-output": "not source\n",
                "roms/private.smp": "not distributable\n",
                "out/archive": "not source\n",
                "sessions/log": "not source\n",
            }
            for name, content in contents.items():
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            subprocess.run(["git", "-C", str(checkout), "add", "-f", "."], check=True)
            (checkout / "src/code.cpp").write_text("working tree modification\n")
            (checkout / "src/generated.h").write_text("generated source\n")
            # This is a typical dangling upstream link to a built test tool.
            if os.name != "nt":
                (checkout / "src/tool-link").symlink_to("not-built-yet")
            package_source.copy_checkout(checkout, copied)
            self.assertTrue((copied / "3rdparty/dependency.c").is_file())
            self.assertTrue((copied / "Makefile.libretro").is_file())
            self.assertEqual((copied / "src/code.cpp").read_text(), "working tree modification\n")
            self.assertTrue((copied / "src/generated.h").is_file())
            for excluded in (".git", "build", "roms", "out", "sessions"):
                self.assertFalse((copied / excluded).exists())
            if os.name != "nt":
                self.assertTrue((copied / "src/tool-link").is_symlink())
                self.assertEqual(os.readlink(copied / "src/tool-link"), "not-built-yet")


if __name__ == "__main__":
    unittest.main()
