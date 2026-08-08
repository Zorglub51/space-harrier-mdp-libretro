#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mame_tree="${1:-${repo_root}/build/mame}"
expected_commit="$(tr -d '[:space:]' < "${repo_root}/MAME_COMMIT")"

if [[ ! -d "${mame_tree}/.git" ]]; then
    mkdir -p "$(dirname "${mame_tree}")"
    git clone --filter=blob:none https://github.com/libretro/mame.git "${mame_tree}"
fi

git -C "${mame_tree}" fetch --depth=1 origin "${expected_commit}"
git -C "${mame_tree}" checkout --detach "${expected_commit}"
"${repo_root}/scripts/prepare-mame.sh" "${mame_tree}"
