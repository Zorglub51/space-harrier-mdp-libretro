#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    printf 'Usage: %s ROM\n' "$0" >&2
    exit 2
fi

pak_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
case "$1" in
    /*) rom=$1 ;;
    *) rom="$PWD/$1" ;;
esac

export HOME="${USERDATA_PATH:?Launch this pak from NextUI}"
mkdir -p "$HOME" "${BIOS_PATH:?}/SHMDP" "${SAVES_PATH:?}/SHMDP" \
    "${CHEATS_PATH:?}/SHMDP" "${LOGS_PATH:?}"
cd "$HOME"
exec minarch.elf "$pak_dir/shmdp_libretro.so" "$rom" >"$LOGS_PATH/SHMDP.txt" 2>&1
