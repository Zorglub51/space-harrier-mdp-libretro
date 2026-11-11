#!/bin/sh
set -eu

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    printf 'Usage: %s ARM64_BUILD OUTPUT_DIR RUNTIME_LICENSES [CAPTURES_DIR]\n' "$0" >&2
    exit 2
fi
scripts=$(CDPATH= cd "$(dirname "$0")" && pwd)
build=$(CDPATH= cd "$1" && pwd)
mkdir -p "$2"
output=$(CDPATH= cd "$2" && pwd)
licenses=$(CDPATH= cd "$3" && pwd)
for license in libcxx libcxxabi libunwind; do
    test -s "$licenses/$license.txt"
done

archive=markv-nextui.zip
if [ "$#" -eq 4 ]; then
    captures=$(CDPATH= cd "$4" && pwd)
    archive=markv-nextui-private.zip
fi
test ! -e "$output/$archive"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
emulator="$stage/Emus/tg5040/MARKV.pak"
benchmark="$stage/Tools/tg5040/Mark V Benchmark.pak"
mkdir -p "$emulator" "$benchmark" "$stage/licenses"
install -m 755 "$scripts/launch-game.sh" "$emulator/launch.sh"
install -m 755 "$scripts/launch-benchmark.sh" "$benchmark/launch.sh"
install -m 755 "$build/markv_libretro.so" "$emulator/markv_libretro.so"
install -m 755 "$build/markv-run" "$benchmark/markv-run"
install -m 755 "$build/markv-replay" "$benchmark/markv-replay"
cp "$licenses/"*.txt "$stage/licenses/"
cp "$scripts/TEST.md" "$stage/MarkV-TEST.md"

if [ "$#" -eq 4 ]; then
    for game in SH1 SH2; do
        mkdir -p "$benchmark/captures/$game"
        cp "$captures/$game/"*.bin "$benchmark/captures/$game/"
    done
fi

cd "$stage"
zip -q -r "$stage/$archive" Emus Tools licenses MarkV-TEST.md
unzip -tq "$stage/$archive"
mv "$stage/$archive" "$output/$archive"
