#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${repo_root}/scripts/package_source.py" \
    "${1:?usage: package-source.sh PREPARED_MAME_TREE}"
