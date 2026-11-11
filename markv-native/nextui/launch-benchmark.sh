#!/bin/sh
set -eu

pak_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
sd_root=$(CDPATH= cd "$pak_dir/../../.." && pwd)
log="$sd_root/MarkV-Benchmark.txt"
exec >"$log" 2>&1

printf 'Mark V benchmark\n'
date
uname -a
freq_dir=/sys/devices/system/cpu/cpu0/cpufreq
for key in scaling_governor scaling_cur_freq scaling_max_freq; do
    if [ -r "$freq_dir/$key" ]; then
        printf '%s=%s\n' "$key" "$(cat "$freq_dir/$key")"
    fi
done

failed=0
ran_rom=0
for rom in "$sd_root/Roms/Space Harrier (MARKV)/"*.smp "$sd_root/Roms/Space Harrier (MARKV)/"*.SMP; do
    [ -f "$rom" ] || continue
    ran_rom=1
    printf '\nMachine benchmark: %s\n' "$(basename "$rom")"
    "$pak_dir/markv-run" --exercise "$rom" 4200 || failed=1
    printf '\nMark VI + Widescreen benchmark: %s\n' "$(basename "$rom")"
    "$pak_dir/markv-run" --exercise --mark-vi --widescreen "$rom" 4200 || failed=1
done
if [ "$ran_rom" -eq 0 ]; then
    printf '\nPlace your .smp files in Roms/Space Harrier (MARKV) to measure the complete machine.\n'
fi

for game in SH1 SH2; do
    set -- "$pak_dir/captures/$game/"*.bin
    [ -f "$1" ] || continue
    printf '\nRaster benchmark: %s\n' "$game"
    "$pak_dir/markv-replay" --bench 32 "$@" || failed=1
done

if [ "$failed" -ne 0 ]; then
    printf '\nBenchmark failed. See the results above.\n'
    exit 1
fi
printf '\nBenchmark complete\n'
