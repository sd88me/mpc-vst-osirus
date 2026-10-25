#!/usr/bin/env bash
# Skin only, no engine build: regenerate layout.conf + the skin folder, then draw every page into vst/preview/<name>/page_N.png.
#   tools/preview.sh [name]      (default "latest"; needs Docker, builds nothing for the device)
set -euo pipefail
cd "$(dirname "$0")/.."
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins}"
OUT="vst/preview/${1:-latest}"
python3 tools/gen_params.py
python3 tools/make_custom.py --install
docker image inspect mpc-vst-html-art >/dev/null 2>&1 || docker build -q -t mpc-vst-html-art "$MPC_VST/tools/html_art" >/dev/null
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -v "$MPC_VST":/mv:ro -w /w mpc-vst-html-art python3 /mv/tools/gen_vst.py vst/vst.json 2>&1 | grep -v "^warning: skin:" || true
mkdir -p "$OUT"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -v "$MPC_VST":/mv:ro -w /w python:3.11-slim sh -c \
  "pip install -q --no-warn-script-location --target /tmp/p pillow >/dev/null 2>&1; PYTHONPATH=/tmp/p python3 /mv/tools/studio.py preview 'vst/build/skin/sd88me - VST - Osirus/Plugin Skins' -o $OUT/page_%d.png" | grep -v open
