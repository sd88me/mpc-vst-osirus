#!/usr/bin/env bash
# Build the release zip (no ROMs in it) and check it against the plugin catalog's rules.
#   ./release.sh <version>            e.g. ./release.sh 0.2.3   -> dist/Osirus-<version>-mpc-aarch64.zip
# Then publish it: gh release create v<version> dist/Osirus-<version>-mpc-aarch64.zip --title "Osirus <version>" --notes-file <notes>
# MPC_VST: checkout of mpc-vst-plugins (default ~/mpc-vst-plugins), on a branch with the skin tool's `vy=` (PR #550 or newer main).
set -euo pipefail
cd "$(dirname "$0")"
VER="${1:?usage: ./release.sh <version>}"
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins}"
./build.sh all
rm -rf "dist/Osirus-$VER-mpc-aarch64.zip"
EXTRA="$(mktemp -d)"; trap 'rm -rf "$EXTRA"' EXIT
cp -r release/osirus/. "$EXTRA/"; cp LICENSE CREDITS.md "$EXTRA/"        # the installed plugin folder carries its licence and credits
python3 "$MPC_VST/tools/release.py" --so vst/build/aarch64/osirus.so --skin "vst/build/skin/sd88me - VST - Osirus" \
  --entry vst/build/pluginlist-entry.xml --version "$VER" --extra "$EXTRA:osirus" \
  --repo sd88me/mpc-vst-osirus --license GPL-3.0-only --id osirus --requires "your own Virus ROM (A, B or C)" -o dist
python3 "$MPC_VST/tools/catalog_check.py" "dist/Osirus-$VER-mpc-aarch64.zip" --catalog --expect-id osirus --expect-repo sd88me/mpc-vst-osirus
# the package must carry no ROM: refuse anything that looks like one
if python3 -I -m zipfile -l "dist/Osirus-$VER-mpc-aarch64.zip" | grep -i -E '\.(bin|mid|syx|rom)\b' | grep -v "PUT_"; then
  echo "refusing: a ROM-like file is in the zip" >&2; exit 1
fi
echo "ok: dist/Osirus-$VER-mpc-aarch64.zip"
