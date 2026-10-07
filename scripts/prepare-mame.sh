#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mame_tree="${1:-${repo_root}/build/mame}"
expected_commit="$(tr -d '[:space:]' < "${repo_root}/MAME_COMMIT")"
patch_file="${repo_root}/patches/mame0289-space-harrier-mdp.patch"
generated_header="${mame_tree}/src/devices/bus/megadrive/sh1_mdp_rom.h"

if [[ ! -d "${mame_tree}/.git" ]]; then
    echo "Not a libretro/MAME checkout: ${mame_tree}" >&2
    exit 1
fi

actual_commit="$(git -C "${mame_tree}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${expected_commit}" ]]; then
    echo "Wrong libretro/MAME revision." >&2
    echo "Expected: ${expected_commit}" >&2
    echo "Actual:   ${actual_commit}" >&2
    exit 1
fi

if git -C "${mame_tree}" apply --check "${patch_file}" 2>/dev/null; then
    git -C "${mame_tree}" apply "${patch_file}"
elif ! git -C "${mame_tree}" apply --reverse --check "${patch_file}"; then
    echo "The MAME tree is neither clean nor already patched." >&2
    exit 1
fi

python3 "${repo_root}/scripts/generate_rom_patch_header.py" \
    "${repo_root}/rompatch/patch.py" \
    "${generated_header}"

for header in "${repo_root}"/src/markv/*.h; do
    cp "${header}" "${mame_tree}/src/devices/bus/megadrive/"
done

echo "Prepared ${mame_tree} for Space Harrier MDP."
