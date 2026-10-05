#!/usr/bin/env bash
set -euo pipefail

# SH_MDP_GAME=sh1 limits the run to Space Harrier; sh2 and all are also accepted.
# SH_MDP_CORE can select a core outside the default build/mame tree.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rom_dir="${SH_MDP_ROM_DIR:?Set SH_MDP_ROM_DIR to the private ROM directory}"
core="${SH_MDP_CORE:-}"
game="${SH_MDP_GAME:-all}"
case "${game}" in
    all|sh1|sh2) ;;
    *) echo "Invalid SH_MDP_GAME: ${game}. Expected all, sh1 or sh2." >&2; exit 1 ;;
esac
frames="${SH_MDP_TEST_FRAMES:-6000}"
baseline_frames="${frames}"
if (( baseline_frames > 1200 )); then
    baseline_frames=1200
fi

if [[ -z "${core}" && -d "${repo_root}/build/mame" ]]; then
    for core_name in shmdp_libretro mame_libretro; do
        core="$(find "${repo_root}/build/mame" -type f \( -name "${core_name}.so" -o -name "${core_name}.dylib" -o -name "${core_name}.dll" \) -print -quit)"
        if [[ -n "${core}" ]]; then
            break
        fi
    done
fi
if [[ -z "${core}" || ! -f "${core}" ]]; then
    echo "Built Libretro core not found. Set SH_MDP_CORE explicitly." >&2
    exit 1
fi

mkdir -p "${repo_root}/test-results"
while IFS='|' read -r selected_game rom report; do
    if [[ "${game}" != all && "${game}" != "${selected_game}" ]]; then
        continue
    fi
    baseline="${repo_root}/test-results/${report%.json}-no-input.json"
    python3 "${repo_root}/tests/libretro_regression.py" \
        --core "${core}" \
        --rom "${rom_dir}/${rom}" \
        --frames "${baseline_frames}" \
        --checkpoints "600,1200" \
        --no-input \
        --output "${baseline}"
    python3 "${repo_root}/tests/libretro_regression.py" \
        --core "${core}" \
        --rom "${rom_dir}/${rom}" \
        --frames "${frames}" \
        --different-from "${baseline}" \
        --output "${repo_root}/test-results/${report}"
done <<'EOF'
sh1|jp_jp_space_harrier.smp|space-harrier.json
sh2|jp_jp_Space_Harrier_II.smp|space-harrier-ii.json
EOF
