#!/usr/bin/env python3
"""Load and run a built core with a generated, original 68000 test cartridge.

No commercial ROM, game artwork or save data is used. This checks the host ABI,
machine startup, software video/audio, save/restore and shutdown. It does not
exercise the authenticated SH1/SH2 adapters or establish gameplay compatibility.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import tempfile

from libretro_regression import Variable
from libretro_state_regression import StateFrontend, roundtrip


def cartridge():
    rom = bytearray(0x10000)
    struct.pack_into('>II', rom, 0, 0xffff00, 0x200)
    rom[0x100:0x110] = b'SEGA MEGA DRIVE '
    rom[0x1f0:0x1f3] = b'JUE'
    struct.pack_into('>IIII', rom, 0x1a0, 0, len(rom) - 1, 0xff0000, 0xffffff)
    # Mask interrupts, release Z80 reset under bus request, initialize the VDP
    # in H40 mode, and increment backdrop colour after each vertical blank.
    words = [0x46fc, 0x2700,
             0x33fc, 0x0100, 0x00a1, 0x1100,
             0x33fc, 0x0100, 0x00a1, 0x1200,
             0x41f9, 0x00c0, 0x0004]
    registers = [0x8004, 0x8144, 0x8230, 0x8334, 0x8407, 0x8578,
                 0x8700, 0x8b00, 0x8c81, 0x8d3f, 0x8f02, 0x9001]
    for value in registers:
        words += [0x30bc, value]  # move.w #value,(a0)
    words += [0x7200]  # moveq #0,d1
    loop = len(words)
    words += [0x3010, 0x0800, 3, 0x67f8]  # wait until VBlank (bit 3)
    words += [0x20bc, 0xc000, 0x0000, 0x3141, 0xfffc, 0x5481]  # CRAM[0]=d1; d1+=2
    words += [0x3010, 0x0800, 3, 0x66f8]  # wait until active display
    displacement = (loop - len(words) - 1) * 2
    words += [0x6000 | (displacement & 255)]
    struct.pack_into('>' + 'H' * len(words), rom, 0x200, *words)
    return bytes(rom)


class SmokeFrontend(StateFrontend):
    def __init__(self, core, rom, directory, threaded):
        self.threaded = b'enabled' if threaded else b'disabled'
        super().__init__(core, rom, 'none')
        self.system_dir = self.save_dir = os.fsencode(directory)

    def environment(self, command, data):
        if command == 15:
            v = C.cast(data, C.POINTER(Variable)).contents
            if v.key == b'mame_thread_mode':
                v.value = self.threaded
                return True
            if v.key in (b'mame_auto_save', b'mame_read_config', b'mame_write_config'):
                v.value = b'disabled'
                return True
        return super().environment(command, data)

    def input_state(self, *args):
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--threaded', action='store_true')
    args = parser.parse_args()
    report = dict(passed=False, platform=platform.platform(), machine=platform.machine(),
                  threaded=args.threaded, core_sha256=hashlib.sha256(args.core.read_bytes()).hexdigest(),
                  scope='Generated cartridge only; authenticated SH1/SH2 paths are not covered.')
    try:
        with tempfile.TemporaryDirectory(prefix='sh-public-smoke-') as temporary:
            root = Path(temporary)
            rom = root / 'smoke.md'
            rom.write_bytes(cartridge())
            frontend = SmokeFrontend(args.core, rom, root, args.threaded)
            roundtrip(frontend, 120, 30, report)
            frames = report['first']['video_frame_hashes']
            if len({f['sha256'] for f in frames}) < 3:
                raise RuntimeError('Generated cartridge did not animate its backdrop')
            if not report['passed']:
                raise RuntimeError('Save-state replay diverged')
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('passed', 'platform', 'threaded', 'core_sha256')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
