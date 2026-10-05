#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mame_tree="${1:?usage: package-core.sh MAME_TREE PLATFORM_TAG}"
platform_tag="${2:?usage: package-core.sh MAME_TREE PLATFORM_TAG}"
version="${PACKAGE_VERSION:-$(tr -d '[:space:]' < "${repo_root}/VERSION")}"
if [[ ! "${version}" =~ ^[[:alnum:]][[:alnum:]._-]*$ ]]; then
    echo "Invalid package version: ${version}" >&2
    exit 1
fi
if [[ ! "${platform_tag}" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]]; then
    echo "Invalid platform tag: ${platform_tag}" >&2
    exit 1
fi
output_dir="${PACKAGE_OUTPUT_DIR:-${repo_root}/out}"
package_dir="${output_dir}/space-harrier-mdp-${version}-${platform_tag}"
archive="${package_dir}.7z"

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
cp "${repo_root}/CHANGELOG.md" "${package_dir}/CHANGELOG.md"
mkdir -p "${package_dir}/docs"
cp "${repo_root}/docs/DEPANNAGE.md" "${package_dir}/docs/"
cp "${repo_root}/docs/TROUBLESHOOTING.md" "${package_dir}/docs/"

if [[ "${platform_tag}" == macos-* ]]; then
    cp "${repo_root}/dist/INSTALLER_MACOS.command" "${package_dir}/INSTALLER_MACOS.command"
    chmod +x "${package_dir}/INSTALLER_MACOS.command"
elif [[ "${platform_tag}" == windows-* ]]; then
    cp "${repo_root}/dist/TESTER_SH1_WINDOWS.cmd" "${package_dir}/"
    cp "${repo_root}/dist/LISEZ_MOI_SH1_WINDOWS.txt" "${package_dir}/"
    if [[ -f "${mame_tree}/windows-source-manifest.json" ]]; then
        mkdir -p "${package_dir}/source-reference"
        cp "${mame_tree}/windows-source-manifest.json" "${package_dir}/source-reference/"
        cp "${mame_tree}/windows-source.patch" "${package_dir}/source-reference/"
        cp "${mame_tree}/windows-source-sh1_mdp_rom.h" "${package_dir}/source-reference/"
        for provenance in windows-portability.patch build-windows-command.txt windows-binary-verification.json; do
            if [[ -f "${mame_tree}/${provenance}" ]]; then
                cp "${mame_tree}/${provenance}" "${package_dir}/source-reference/"
            fi
        done
    fi
fi

python3 - "${package_dir}" "${extension}" "${version}" "${platform_tag}" "${repo_root}" "${mame_tree}" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
import subprocess

package, extension, version, platform, repo, mame = sys.argv[1:]
package, repo, mame = Path(package), Path(repo), Path(mame)
def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None
core = package / f"shmdp_libretro.{extension}"
digest = hashlib.sha256(core.read_bytes()).hexdigest()
(package / "CORE_SHA256.txt").write_text(f"{digest}  {core.name}\n", encoding="utf-8")
info = package / "shmdp_libretro.info"
lines = info.read_text(encoding="utf-8").splitlines()
info.write_text("\n".join(
    f'display_version = "{version} (MAME 0.289)"'
    if line.startswith("display_version =") else line for line in lines
) + "\n", encoding="utf-8")
(package / "BUILD.json").write_text(json.dumps({
    "schema_version": 1,
    "kind": "core",
    "package_version": version,
    "platform": platform,
    "core_sha256": digest,
    "source_commit": git(repo, "rev-parse", "HEAD"),
    "source_tree_dirty": bool(git(repo, "status", "--porcelain")),
    "mame_commit": (repo / "MAME_COMMIT").read_text().strip(),
    "mame_tree_commit": git(mame, "rev-parse", "HEAD"),
    "rom_patch_table_sha256": hashlib.sha256((repo / "rompatch/patch.py").read_bytes()).hexdigest(),
}, indent=2) + "\n", encoding="utf-8")
PY

python3 "${repo_root}/scripts/package_archive.py" "${package_dir}" "${archive}"
