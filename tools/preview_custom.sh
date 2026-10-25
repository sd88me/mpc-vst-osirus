#!/usr/bin/env bash
# Offline preview of the custom layout (tools/make_custom.py): vst/custom/preview/page_N.png
set -euo pipefail
cd "$(dirname "$0")/.."
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins}"
python3 tools/make_custom.py >/dev/null
docker image inspect mpc-vst-html-art >/dev/null 2>&1 || docker build -q -t mpc-vst-html-art "$MPC_VST/tools/html_art" >/dev/null
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -v "$MPC_VST":/mv:ro -w /w mpc-vst-html-art python3 /mv/tools/gen_vst.py vst/custom/vst.json 2>&1 | grep -v "^warning: skin:" || true
mkdir -p vst/custom/preview
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -v "$MPC_VST":/mv:ro -w /w python:3.11-slim sh -c \
  "pip install -q --no-warn-script-location --target /tmp/p pillow >/dev/null 2>&1; PYTHONPATH=/tmp/p python3 /mv/tools/studio.py preview 'vst/custom/build/skin/sd88me - VST - Osirus Custom/Plugin Skins' -o vst/custom/preview/page_%d.png" | grep -v open
