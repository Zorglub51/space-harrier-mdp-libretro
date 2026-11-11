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

mkdir -p "${BIOS_PATH:?}/MARKV" "${SAVES_PATH:?}/MARKV" "${CHEATS_PATH:?}/MARKV" "${LOGS_PATH:?}"
cd "${USERDATA_PATH:?Launch this pak from NextUI}"
exec minarch.elf "$pak_dir/markv_libretro.so" "$rom" >"$LOGS_PATH/MARKV.txt" 2>&1
