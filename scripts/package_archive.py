#!/usr/bin/env python3
"""Create verified 7z downloads, with an optional local download-size limit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


VOLUME_SIZE = 9_500_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_7z(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)


def package_archive(package: Path, archive: Path, download_limit: int = None) -> list[Path]:
    package, archive = package.resolve(), archive.resolve()
    if download_limit is None:
        download_limit = int(os.environ.get("PACKAGE_MAX_DOWNLOAD_BYTES", "0"))
    if download_limit < 0 or download_limit == 1:
        raise RuntimeError("PACKAGE_MAX_DOWNLOAD_BYTES must be zero or at least 2.")
    seven_zip = shutil.which("7zz") or shutil.which("7z")
    if not seven_zip:
        raise RuntimeError("7-Zip is required: install 7zz or 7z before packaging.")
    if not (package / "BUILD.json").is_file():
        raise RuntimeError(f"Missing package metadata: {package / 'BUILD.json'}")
    archive.parent.mkdir(parents=True, exist_ok=True)

    manifest = package / "FILES_SHA256SUMS"
    files = sorted(path for path in package.rglob("*")
                   if path.is_file() and path != manifest)
    manifest.write_text("".join(
        f"{sha256(path)}  {path.relative_to(package).as_posix()}\n" for path in files
    ), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix=".package-", dir=archive.parent) as temp:
        temp = Path(temp)
        compressed = temp / archive.name
        command = [seven_zip, "a", "-t7z", "-mx=9", "-m0=lzma2", "-md=64m",
                   "-mfb=273", "-ms=on", "-mmt=2", "-snl"]
        if download_limit:
            volume_size = min(VOLUME_SIZE, max(1, download_limit * 95 // 100))
            command.append(f"-v{volume_size}b")
        run_7z(command + [str(compressed), package.name], package.parent)
        if download_limit:
            # Local opt-in only. 7z volumes are contiguous archive bytes, so
            # join them if the result fits the limit; verify the joined archive.
            volumes = sorted(temp.glob(archive.name + ".*"),
                             key=lambda path: int(path.suffix[1:]))
            if not volumes:
                raise RuntimeError("7-Zip did not produce any archive volumes.")
            if sum(path.stat().st_size for path in volumes) < download_limit:
                with compressed.open("wb") as joined:
                    for volume in volumes:
                        with volume.open("rb") as source:
                            shutil.copyfileobj(source, joined)
                        volume.unlink()
                outputs = [compressed]
            else:
                outputs = volumes
            if any(path.stat().st_size >= download_limit for path in outputs):
                raise RuntimeError("A generated download exceeds the size limit.")
        else:
            # GitHub releases use complete archives without an artificial cap.
            outputs = [compressed]
        run_7z([seven_zip, "t", str(outputs[0])], temp)

        metadata = temp / (archive.name + ".BUILD.json")
        build = json.loads((package / "BUILD.json").read_text(encoding="utf-8"))
        build.update({
            "archive_format": "7z",
            "split": len(outputs) > 1,
            "archive_files": [
                {"name": path.name, "size_bytes": path.stat().st_size,
                 "sha256": sha256(path)} for path in outputs
            ],
        })
        metadata.write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
        outputs.append(metadata)
        checksums = temp / (archive.name + ".SHA256SUMS")
        checksums.write_text("".join(
            f"{sha256(path)}  {path.name}\n" for path in outputs
        ), encoding="utf-8")
        outputs.append(checksums)

        # Replace only this package's previous delivery after verification.
        for previous in archive.parent.glob(archive.name + "*"):
            suffix = previous.name[len(archive.name):]
            if suffix in ("", ".BUILD.json", ".SHA256SUMS", ".sha256") or (
                    suffix.startswith(".") and suffix[1:].isdigit()):
                previous.unlink()
        delivered = []
        for path in outputs:
            target = archive.parent / path.name
            shutil.move(str(path), target)
            delivered.append(target)
        return delivered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    for path in package_archive(args.package, args.archive):
        print(f"{path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
