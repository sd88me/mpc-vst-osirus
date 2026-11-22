#!/usr/bin/env bash
# The release zips, from the release build (build/sdk/"sd88me - VST - Osirus", made by ./build-sdk.sh):
#   dist/Osirus-<ver>-mpc-aarch64.zip   install.sh / uninstall.sh for 64-bit MPCs (mpc-vst-plugins' tools/release.py): upgrades 0.2.x in place
#   dist/Osirus-<ver>-mpc-sdk.zip       the one plugin folder for "VST2 Plugins" (tools/sdk_zip.py)
# As in 0.2.x the .so is osirus.so at the folder root with osirus/ beside it (the plugin finds its data there). User data, kept on upgrade
# and uninstall: osirus/roms, osirus/banks, osirus/favourites.dat. No ROM or bank is ever packed. MPC_VST: mpc-vst-plugins with tools/sdk_zip.py.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins-postlaunch}"
[ -f "$MPC_VST/tools/release.py" ] && [ -f "$MPC_VST/tools/sdk_zip.py" ] || { echo "need mpc-vst-plugins with tools/sdk_zip.py (MPC_VST)" >&2; exit 1; }
DIR="sd88me - VST - Osirus"; SRC="$here/build/sdk/$DIR"
[ -f "$SRC/VST/osirus-arm64.so" ] || { echo "missing $SRC: run ./build-sdk.sh first" >&2; exit 1; }
VER=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$SRC/plugin.json")
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); sys.exit(0 if m["uid"]=="OsrS" and "Beta" not in m["name"] else "not the release identity")' "$SRC/plugin.json"
out="$here/dist"; mkdir -p "$out"
st="$here/build/catalog/aarch64"; rm -rf "$st"; mkdir -p "$st/$DIR" "$st/extra"
cp -r "$SRC/Plugin Skins" "$SRC/version.xml" "$st/$DIR/"
python3 - "$SRC/plugin.json" "$st/$DIR/plugin.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m.pop("file32", None)
m["file64"] = "osirus.so"
json.dump(m, open(sys.argv[2], "w"), indent=2)
PY
cp "$SRC/VST/osirus-arm64.so" "$st/osirus.so"
cp -r "$here/release/osirus/." "$st/extra/"; cp "$here/LICENSE" "$here/CREDITS.md" "$st/extra/"
# nothing of the user's may ride along: only the placeholders
if find "$st" -type f | grep -v -E 'PUT_[A-Z_]+_HERE\.txt$' | grep -i -E '/(roms|banks)/|\.(bin|syx|mid)$|favourites'; then
  echo "refusing: user files in the package" >&2; exit 1
fi
printf '<PLUGIN name="Osirus" descriptiveName="Osirus" format="VST" category="Synth" manufacturer="sd88me" version="%s" file="osirus.so" uid="4f737253" isInstrument="1" fileTime="0" infoUpdateTime="0" numInputs="0" numOutputs="2" isShell="0"/>\n' "$VER" > "$st/entry.xml"
python3 "$MPC_VST/tools/release.py" --so "$st/osirus.so" --skin "$st/$DIR" --entry "$st/entry.xml" --version "$VER" --extra "$st/extra:osirus" \
  --user-data osirus/roms --user-data osirus/banks --user-data osirus/favourites.dat --user-files "$here/release/userfiles.json" \
  --repo sd88me/mpc-vst-osirus --license GPL-3.0-only --id osirus --requires "your own Virus ROM (A, B or C)" \
  --about "Access Virus A/B/C emulation with a native MPC panel, your own SysEx sound banks in sub-folders, RANDOM and named favourites." \
  -o "$st/dist"
z=$(ls "$st/dist"/*.zip); cp "$z" "$out/Osirus-$VER-mpc-aarch64.zip"
python3 "$MPC_VST/tools/catalog_check.py" "$out/Osirus-$VER-mpc-aarch64.zip" --catalog --expect-id osirus --expect-repo sd88me/mpc-vst-osirus
python3 "$MPC_VST/tools/sdk_zip.py" "$out/Osirus-$VER-mpc-sdk.zip" "$out/Osirus-$VER-mpc-aarch64.zip"
for f in "$out/Osirus-$VER-mpc-aarch64.zip" "$out/Osirus-$VER-mpc-sdk.zip"; do   # last guard: no ROM-like file in either zip
  if python3 -I -m zipfile -l "$f" | grep -i -E '\.(bin|syx|rom)\b|\.mid\b' | grep -v PUT_; then echo "refusing: a ROM-like file in $f" >&2; exit 1; fi
done
ls -la "$out"/Osirus-"$VER"-mpc-*.zip
