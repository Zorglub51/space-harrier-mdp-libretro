"""Reject incomplete releases and notes that do not match their tag."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notes = load("release-notes")
assets = load("verify-release-assets")


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "VERSION").write_text("0.1.3\n")
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.1.3] - 2026-10-05\n\nCorrected text.\n\n"
            "## [0.1.1] - 2026-08-08\n\nPrevious release.\n")

    def test_only_requested_revision_becomes_release_notes(self):
        self.assertEqual(notes.release_notes(self.root, "v0.1.3"), "Corrected text.\n")

    def test_wrong_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            notes.release_notes(self.root, "v0.1.2")

    def test_missing_empty_and_duplicate_entries_are_rejected(self):
        for body in ("# Changelog\n", "## [0.1.3] - 2026-10-05\n",
                     "## [0.1.3] - 2026-10-05\nA\n## [0.1.3] - 2026-10-05\nB\n"):
            with self.subTest(body=body):
                (self.root / "CHANGELOG.md").write_text(body)
                with self.assertRaises(ValueError):
                    notes.release_notes(self.root, "v0.1.3")


class ReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.commit = "a" * 40
        for platform in assets.PLATFORMS:
            name = f"space-harrier-mdp-0.1.3-{platform}.7z"
            archive = self.root / name
            archive.write_bytes(b"fixture for manifest checks, not an actual 7z")
            manifest = self.root / (name + ".BUILD.json")
            manifest.write_text(json.dumps({
                "schema_version": 1, "kind": "source" if platform == "source" else "core",
                "platform": platform, "package_version": "0.1.3", "source_commit": self.commit,
                "source_tree_dirty": False, "archive_format": "7z", "split": False,
                "archive_files": [{"name": name, "size_bytes": archive.stat().st_size,
                                   "sha256": assets.sha256(archive)}],
            }))
            (self.root / (name + ".SHA256SUMS")).write_text(
                f"{assets.sha256(archive)}  {name}\n{assets.sha256(manifest)}  {manifest.name}\n")

    def verify(self):
        return assets.verify_assets(self.root, "0.1.3", self.commit)

    def test_complete_matrix_is_accepted(self):
        self.assertEqual(len(self.verify()), 5)

    def test_missing_platform_is_rejected(self):
        next(self.root.glob("*.BUILD.json")).unlink()
        with self.assertRaises(ValueError):
            self.verify()

    def test_mixed_revision_dirty_checkout_or_split_download_is_rejected(self):
        manifest = next(self.root.glob("*.BUILD.json"))
        original = json.loads(manifest.read_text())
        for key, value in (("package_version", "0.1.2"), ("source_commit", "b" * 40),
                           ("source_tree_dirty", True), ("split", True)):
            with self.subTest(key=key):
                manifest.write_text(json.dumps(dict(original, **{key: value})))
                with self.assertRaises(ValueError):
                    self.verify()

    def test_corrupted_archive_is_rejected(self):
        next(self.root.glob("*.7z")).write_bytes(b"damaged download")
        with self.assertRaises(ValueError):
            self.verify()

    def test_corrupted_checksums_are_rejected(self):
        next(self.root.glob("*.SHA256SUMS")).write_text("0" * 64 + "  unknown\n")
        with self.assertRaises(ValueError):
            self.verify()

    def test_unexpected_extra_download_is_rejected(self):
        (self.root / "unintended.zip").write_bytes(b"extra")
        with self.assertRaises(ValueError):
            self.verify()

    def test_remote_inventory_rejects_stale_or_partial_draft_assets(self):
        uploaded = [{"name": p.name, "size": p.stat().st_size} for p in self.root.iterdir()]
        assets.verify_uploaded(self.root, uploaded)
        for invalid in (uploaded[:-1], uploaded + [{"name": "old.zip", "size": 12}]):
            with self.assertRaises(ValueError):
                assets.verify_uploaded(self.root, invalid)


if __name__ == "__main__":
    unittest.main()
