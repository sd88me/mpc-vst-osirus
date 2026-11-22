#!/usr/bin/env bash
# Offline x86 test under ASan/UBSan (no device): the native front end + the real engine and your ROM, driven by tests/host_test.cpp in
# real time. Must print OK. OSIRUS_ROMS: a folder with your Virus ROM (default ~/roms/virus/Access Virus C (am29f040b_6v6)). OSIRUS_NAME: the build's name (beta tests).
set -euo pipefail
cd "$(dirname "$0")/.."
SDK="${MPC_SDK:-$HOME/mpc-plugin-builder-sdk}"
MV="${MPC_VST:-$HOME/mpc-vst-plugins}"
ROMS="$(cd "${OSIRUS_ROMS:-$HOME/roms/virus/Access Virus C (am29f040b_6v6)}" && pwd)"
python3 tools/gen_sdk_params.py >/dev/null
# A project chunk saved by the released 0.2.11 build, made from that build's own code and your ROM (not committed: it holds a ROM sound).
[ -f tests/data/legacy-0.2.11.chunk ] || OSIRUS_ROMS="$ROMS" tests/make_legacy_chunk.sh >/dev/null 2>&1
# the engine (unsanitised, Release) for x86, in its own build dir: vst/build/engine/ holds the aarch64 archive
cmake -S . -B build/x86 -G Ninja -DCMAKE_BUILD_TYPE=Release -DMPC_VST="$MV" >/dev/null
cmake --build build/x86 --target osirus_dsp -j"$(nproc)" > build/engine-x86.log 2>&1 || { grep -E "error" build/engine-x86.log | head -20; exit 1; }
B=build/x86; libs=""
for l in libosirus_dsp.a virusLib/libvirusLib.a synthLib/libsynthLib.a baseLib/libbaseLib.a libresample/libresample.a dsp56kEmu/libdsp56kEmu.a dsp56kBase/libdsp56kBase.a asmjit/libasmjit.a vtuneSdk/libvtuneSdk.a; do libs="$libs $B/$l"; done
T=build/test; mkdir -p "$T"
S="-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer -O1 -g -std=c++17 -pthread"
N="${OSIRUS_NAME:-Osirus}"
g++ $S -Wall -Wextra -DOSIRUS_TEST -DOSIRUS_NAME="\"$N\"" -I"$SDK/framework" -I"$MV/wrapper" -Isrc -c src/OsirusPlugin.cpp -o "$T/plugin.o"
g++ $S -DOSIRUS_EXPECT_NAME="\"$N\"" -I"$SDK/framework" -Isrc -c tests/host_test.cpp -o "$T/host_test.o"
g++ $S -o "$T/ostest" "$T/plugin.o" "$T/host_test.o" -Wl,--start-group $libs -Wl,--end-group -ldl -lm
pf="$(mktemp -d)"; trap 'rm -rf "$pf"' EXIT
mkdir -p "$pf/VST/osirus"; mkdir -p "$pf/VST/osirus/roms"; for f in "$ROMS"/*; do case "$f" in *Zone.Identifier) ;; *) cp "$f" "$pf/VST/osirus/roms/";; esac; done; cp plugin.json "$pf/"
[ -n "${OSIRUS_FAVS:-}" ] && cp "$OSIRUS_FAVS" "$pf/VST/osirus/favourites.dat"   # a favourites file (the insert check needs some stored)
set +e
MPC_PLUGIN_FOLDER="$pf" ASAN_OPTIONS=detect_leaks=1 "$T/ostest" tests/data/legacy-0.2.11.chunk > "$T/log.txt" 2>&1
st=$?
grep -E '^(== |  ok   |  FAIL |OK$|FAILED|[A-DUW]: opened|    \(|    [A-Za-z0-9_]+ host )|ERROR: |runtime error' "$T/log.txt" | tail -${TAIL:-120}
exit $st
