#!/usr/bin/env python3
"""Validate a complete, same-revision release before making it public."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PLATFORMS = {"windows-x86_64", "linux-x86_64", "macos-x86_64", "macos-arm64", "source"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_assets(directory: Path, version: str, commit: str):
    manifests = sorted(directory.glob("*.7z.BUILD.json"))
    if len(manifests) != len(PLATFORMS):
        raise ValueError("A release requires four core manifests and one source manifest")
    seen, expected_files, archives = set(), set(), []
    for manifest in manifests:
        build = json.loads(manifest.read_text(encoding="utf-8"))
        platform = build["platform"]
        if platform not in PLATFORMS or platform in seen:
            raise ValueError(f"Unexpected or duplicated platform: {platform}")
        seen.add(platform)
        if build.get("schema_version") != 1 or build.get("kind") != ("source" if platform == "source" else "core"):
            raise ValueError(f"Invalid manifest schema/kind: {manifest.name}")
        if build["package_version"] != version or build["source_commit"] != commit:
            raise ValueError(f"Release revision mismatch: {manifest.name}")
        if build.get("source_tree_dirty") is not False:
            raise ValueError(f"Release was packaged from a dirty checkout: {manifest.name}")
        if build.get("archive_format") != "7z" or build.get("split") is not False:
            raise ValueError("GitHub releases require complete, unsplit 7z archives")
        name = f"space-harrier-mdp-{version}-{platform}.7z"
        entries = build["archive_files"]
        if len(entries) != 1 or entries[0]["name"] != name or manifest.name != name + ".BUILD.json":
            raise ValueError(f"Unexpected archive filename for {platform}")
        archive = directory / name
        if not archive.is_file() or archive.stat().st_size <= 0:
            raise ValueError(f"Missing or empty archive: {name}")
        if archive.stat().st_size != entries[0]["size_bytes"] or sha256(archive) != entries[0]["sha256"]:
            raise ValueError(f"Archive size/hash mismatch: {name}")
        sums = directory / (name + ".SHA256SUMS")
        expected_sums = {name: sha256(archive), manifest.name: sha256(manifest)}
        actual_sums = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            digest, filename = line.split("  ", 1)
            if filename in actual_sums:
                raise ValueError(f"Duplicate checksum entry: {filename}")
            actual_sums[filename] = digest
        if actual_sums != expected_sums:
            raise ValueError(f"Checksum manifest mismatch: {sums.name}")
        expected_files.update((archive.name, manifest.name, sums.name))
        archives.append(archive)
    if {path.name for path in directory.iterdir()} != expected_files:
        raise ValueError("Unexpected files in release download directory")
    return archives


def verify_uploaded(directory, uploaded):
    expected = {path.name: path.stat().st_size for path in directory.iterdir()}
    actual = {asset["name"]: asset["size"] for asset in uploaded}
    if len(uploaded) != len(actual) or actual != expected:
        raise ValueError("Uploaded assets do not match the verified local downloads")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--seven-zip", default=shutil.which("7zz") or shutil.which("7z"))
    parser.add_argument("--uploaded-json", type=Path)
    args = parser.parse_args()
    if args.uploaded_json:
        verify_uploaded(args.directory, json.loads(args.uploaded_json.read_text()))
        print("Uploaded release inventory verified")
        return
    if not args.seven_zip:
        parser.error("7zz or 7z is required to verify release archives")
    archives = verify_assets(args.directory, args.version, args.commit)
    for path in archives:
        subprocess.run([args.seven_zip, "t", str(path)], check=True, stdout=subprocess.DEVNULL)
    print(f"Verified {len(archives)} complete archives for {args.version} at {args.commit}")


if __name__ == "__main__":
    main()
