#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
retroarch_root="${HOME}/Library/Application Support/RetroArch"
retroarch_config="${retroarch_root}/config/retroarch.cfg"

if pgrep -x RetroArch >/dev/null 2>&1; then
    echo "Fermez complètement RetroArch, puis relancez cet installateur."
    echo "Close RetroArch completely, then run this installer again."
    read -r -p "Appuyez sur Entrée pour fermer / Press Return to close. "
    exit 1
fi

read_setting() {
    local key="$1"
    if [[ -f "${retroarch_config}" ]]; then
        sed -n "s|^${key} = \"\(.*\)\"$|\1|p" "${retroarch_config}" | tail -n 1
    fi
}

expand_home() {
    case "$1" in
        "~/"*) printf '%s/%s\n' "${HOME}" "${1#\~/}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

cores_raw="$(read_setting libretro_directory)"
info_raw="$(read_setting libretro_info_path)"
cores_dir="$(expand_home "${cores_raw:-${retroarch_root}/cores}")"
info_dir="$(expand_home "${info_raw:-${retroarch_root}/info}")"

mkdir -p "${cores_dir}" "${info_dir}"
cp "${script_dir}/shmdp_libretro.dylib" "${cores_dir}/shmdp_libretro.dylib"
cp "${script_dir}/shmdp_libretro.info" "${info_dir}/shmdp_libretro.info"

# RetroArch otherwise keeps showing the filename and ignores newly installed
# .info files until this generated cache is rebuilt.
rm -f "${info_dir}/core_info.cache"

echo
echo "Space Harrier MDP est installé. Relancez RetroArch."
echo "Space Harrier MDP is installed. Restart RetroArch."
read -r -p "Appuyez sur Entrée pour fermer / Press Return to close. "
