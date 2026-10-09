#!/usr/bin/env python3
"""Compare an unobstructed SH1 sky column with BOTH original ROM phases.

Private inputs: authenticated original ROM, a big-endian FF0000..FFFFFF RAM
snapshot during a stable scene, and consecutive raw 320x224 frontend PNGs.
The RAM supplies the palette/table pointers and offsets; it is not an expected
framebuffer. By default this compares ROM data. --native-oracle instead uses
CRAM samples produced by Sh1SkyCpuOracle.java executing the original M2 CPU.
Neither mode is a recording of the complete original M2 application.
The selected column/rows must contain only sky, without text, tiles or sprites.
Requires Pillow. Never use shader-processed or scaled screenshots.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image

SH1_SHA1 = "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72"
M2_SHA256 = "2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f"


def native_phases(report, rom, ram, top, bottom):
    """Use the native execution report without aligning or shifting any rows."""
    if (report.get("schema") != 1 or report.get("binary_sha256") != M2_SHA256
            or report.get("rom_sha1") != hashlib.sha1(rom).hexdigest()
            or report.get("ram_sha256") != hashlib.sha256(ram).hexdigest()):
        raise ValueError("Native report identity does not match the supplied inputs")
    cases = report.get("cases", [])
    if len(cases) != 2 or [case["input_phase"] for case in cases] != [0, 1]:
        raise ValueError("Expected both native sky phases")
    phases = []
    for case in cases:
        rows = case["rows"]
        if [row["line"] for row in rows] != list(range(-8, 224)):
            raise ValueError("Incomplete native render-line sequence")
        if case["output_phase"] != case["input_phase"] + 1:
            raise ValueError("Native phase counter did not advance")
        writes = case["writes"]
        if (len(writes) != 112 or [w["line"] for w in writes] != list(range(1, 224, 2))
                or any(w["address"] != 0xC00400 for w in writes)):
            raise ValueError("Incomplete native sky-write sequence")
        phases.append([tuple(((row["cram"] >> bit) & 7) * 34 for bit in (1, 5, 9))
                       for row in rows if top <= row["line"] < bottom])
    return phases


def sky_phases(rom, ram, top, bottom):
    if hashlib.sha1(rom).hexdigest() != SH1_SHA1:
        raise ValueError("Expected the authenticated original SH1 ROM")
    if len(ram) != 0x10000:
        raise ValueError("RAM must contain FF0000..FFFFFF in guest byte order")
    if not 0 <= top < bottom <= 224:
        raise ValueError("Expected 0 <= top < bottom <= 224")
    palette, table = struct.unpack_from(">II", ram, 0x4060)
    offset, scroll = struct.unpack_from(">hh", ram, 0x4068)
    if not 0 <= palette <= len(rom) - 32:
        raise ValueError("Captured palette is outside the ROM")
    colours = struct.unpack_from(">16H", rom, palette)
    phases = []
    for shift in (0, 4):
        rows = []
        for y in range(top, bottom):
            address = table + offset + scroll + y // 2
            if not 0 <= address < len(rom):
                raise ValueError("Captured sky table is outside the ROM")
            cram = colours[(rom[address] >> shift) & 15]
            # Native C1E24 packing + registered 229E08 RGB888 conversion.
            rows.append(tuple(((cram >> bit) & 7) * 34 for bit in (1, 5, 9)))
        phases.append(rows)
    return phases


def check(paths, phases, x, top, bottom):
    if not paths:
        raise ValueError("No PNG captures selected")
    if not 0 <= x < 320:
        raise ValueError("Expected 0 <= x < 320")
    counts = Counter()
    failures, sequence = [], []
    for path in paths:
        with Image.open(path) as image:
            if image.size != (320, 224):
                raise ValueError(f"{path}: expected raw 320x224 pixels")
            image = image.convert("RGB")
            column = [image.getpixel((x, y)) for y in range(top, bottom)]
        differences = [sum(a != b for a, b in zip(column, phase)) for phase in phases]
        matching = [i for i, difference in enumerate(differences) if difference == 0]
        label = "/".join(map(str, matching)) if matching else "mismatch"
        counts[label] += 1
        sequence.append(label)
        if not matching:
            failures.append({"capture": path.name, "different_rows_per_phase": differences})
    return {"passed": not failures, "frames": len(paths), "rows_per_frame": bottom - top,
            "phase_counts": dict(counts), "phase_sequence": sequence, "failures": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--ram", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    parser.add_argument("--x", type=int, required=True)
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--bottom", type=int, default=144, help="exclusive")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--native-oracle", type=Path,
                        help="Private JSON output from Sh1SkyCpuOracle.java")
    args = parser.parse_args()
    rom, ram = args.rom.read_bytes(), args.ram.read_bytes()
    if args.last < args.first:
        parser.error("last must not precede first")
    paths = [args.captures / f"full-{i:05d}.png" for i in range(args.first, args.last + 1)]
    phases = sky_phases(rom, ram, args.top, args.bottom)
    boundary = "Original ROM phase data versus raw core pixels; no native CPU execution"
    if args.native_oracle:
        phases = native_phases(json.loads(args.native_oracle.read_text()), rom, ram,
                               args.top, args.bottom)
        boundary = ("Original M2 CPU sky/IRQ execution versus raw core sky pixels; "
                    "isolated workload, no complete original game or presentation")
    result = check(paths, phases, args.x, args.top, args.bottom)
    result.update({"boundary": boundary,
                   "rom_sha1": hashlib.sha1(rom).hexdigest(),
                   "ram_sha256": hashlib.sha256(ram).hexdigest(),
                   "column": args.x, "top": args.top, "bottom": args.bottom})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("passed", "frames", "phase_counts", "failures")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
