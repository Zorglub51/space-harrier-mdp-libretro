#!/usr/bin/env python3
"""Compare SH1 host emission to private paired native-constructor captures.

Input ROM must have the compatibility instructions restored. Each ram-NNNNN.bin
is 128 KiB of big-endian FE0000..FFFFFF at the FF40B8 read by 170344/170476;
end-NNNNN.bin is the same range at native PC 170836 after construction. Neither
input is included in the public repository. Counts/hashes alone can be shared.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

from test_sh1_markvi import compile_probe
from test_sh2_markvi import run_probe


def check(rom, directory, probe):
    def word(ram, address):
        p = address - 0xfe0000
        if not 0 <= p < len(ram)-1:
            raise ValueError(f'invalid captured address {address:06x}')
        return int.from_bytes(ram[p:p+2], 'big')

    def longword(ram, address):
        return word(ram, address)*65536 + word(ram, address+2)

    frames = []
    for path in sorted(directory.glob('ram-*.bin')):
        end_path = path.with_name(path.name.replace('ram-', 'end-'))
        if not end_path.exists():
            raise ValueError(f'missing native completion for {path.name}')
        entry, end = path.read_bytes(), end_path.read_bytes()
        if len(entry) != 0x20000 or len(end) != 0x20000:
            raise ValueError('captures must contain all 128 KiB, in guest byte order')
        emitted = run_probe(probe, rom, entry)
        if emitted is None:
            raise ValueError(f'host rejected snapshot {path.name}')
        pool = Counter(emitted)
        bank = word(entry, 0xff1be0) & 1
        if bank:
            groups = [(0xff1ec8, word(end, 0xff3bf6)),
                      (longword(end, 0xff120c), word(end, 0xff3bf4)),
                      (0xff195e, word(end, 0xff3bec))]
            transforms = 0xff1dc8
        else:
            groups = [(longword(end, 0xff1210), word(end, 0xff3bfa)),
                      (longword(end, 0xff1450), word(end, 0xff3bf8)),
                      (0xff16dc, word(end, 0xff3bee))]
            transforms = 0xff1cc6
        native_count = unmatched = 0
        for source, count in groups:
            for i in range(count):
                p = source + 8*i
                x = word(end, p+6)
                transform = x >> 9
                zoom = word(end, transforms+transform*2) if transform else 0x1000
                record = (word(end,p), word(end,p+2)&0xff00, word(end,p+4), x&511, zoom)
                if record[:4] == (0,0,0,0):
                    continue  # The native constructor's empty-list sentinel.
                native_count += 1
                if pool[record]:
                    pool[record] -= 1
                else:
                    unmatched += 1
        frames.append({'capture': path.name, 'bank': bank,
                       'entry_sha256': hashlib.sha256(entry).hexdigest(),
                       'native_count': native_count, 'host_count': len(emitted),
                       'unmatched_native_records': unmatched})
    if not frames:
        raise ValueError('no paired captures found')
    return {'rom_sha256': hashlib.sha256(rom).hexdigest(),
            'frames': len(frames),
            'native_records': sum(f['native_count'] for f in frames),
            'unmatched_native_records': sum(f['unmatched_native_records'] for f in frames),
            'extra_host_records': sum(f['host_count']-f['native_count'] for f in frames),
            'maximum_host_records': max(f['host_count'] for f in frames),
            'samples': frames}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('restored_rom', type=Path)
    parser.add_argument('captures', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        probe, _ = compile_probe(tmp)
        report = check(args.restored_rom.read_bytes(), args.captures, probe)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}, indent=2))
    return int(bool(report['unmatched_native_records']))


if __name__ == '__main__':
    raise SystemExit(main())
