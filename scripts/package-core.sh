#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mame_tree="${1:?usage: package-core.sh MAME_TREE PLATFORM_TAG}"
platform_tag="${2:?usage: package-core.sh MAME_TREE PLATFORM_TAG}"
version="$(tr -d '[:space:]' < "${repo_root}/VERSION")"
package_dir="${repo_root}/out/space-harrier-mdp-${version}-${platform_tag}"
archive="${package_dir}.zip"

case "${platform_tag}" in
    windows-*) extension=dll ;;
    macos-*) extension=dylib ;;
    linux-*) extension=so ;;
    *) echo "Unknown platform tag: ${platform_tag}" >&2; exit 1 ;;
esac

core="$(find "${mame_tree}" -type f \( -name "shmdp_libretro.${extension}" -o -name "mame_libretro.${extension}" \) -print -quit)"
if [[ -z "${core}" ]]; then
    echo "Built core not found in ${mame_tree}." >&2
    exit 1
fi

rm -rf "${package_dir}"
mkdir -p "${package_dir}"
cp "${core}" "${package_dir}/shmdp_libretro.${extension}"
cp "${repo_root}/dist/shmdp_libretro.info" "${package_dir}/shmdp_libretro.info"
cp "${repo_root}/GUIDE_UTILISATEUR.md" "${package_dir}/LISEZ-MOI.md"
cp "${repo_root}/USER_GUIDE.md" "${package_dir}/README.md"
cp "${repo_root}/LICENSE" "${package_dir}/LICENSE"
cp "${repo_root}/COPYING.MAME" "${package_dir}/COPYING.MAME"
cp "${repo_root}/NOTICE.md" "${package_dir}/NOTICE.md"

if [[ "${platform_tag}" == macos-* ]]; then
    cp "${repo_root}/dist/INSTALLER_MACOS.command" "${package_dir}/INSTALLER_MACOS.command"
    chmod +x "${package_dir}/INSTALLER_MACOS.command"
fi

mkdir -p "${repo_root}/out"
rm -f "${archive}"
(cd "${repo_root}/out" && zip -9 -r "$(basename "${archive}")" "$(basename "${package_dir}")")
echo "${archive}"
