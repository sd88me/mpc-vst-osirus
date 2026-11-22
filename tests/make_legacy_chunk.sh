#!/usr/bin/env bash
# Make tests/data/legacy-0.2.11.chunk: what a project saved with the released 0.2.11 build stores (effGetChunk), from that build's own code.
# Builds the v0.2.11 tree (engine + the mpc-vst-plugins wrapper as of the release day) for x86 as a shared library, loads it like a host
# with your ROM, and saves the chunk. Not committed: it carries ROM sound bytes (the patch). OSIRUS_ROMS: a folder with a Virus ROM
# (default ~/roms/virus/Access Virus C (am29f040b_6v6)).
set -euo pipefail
cd "$(dirname "$0")/.."
MV="${MPC_VST:-$HOME/mpc-vst-plugins}"
ROMS="$(cd "${OSIRUS_ROMS:-$HOME/roms/virus/Access Virus C (am29f040b_6v6)}" && pwd)"
W=build/legacy; rm -rf "$W"; mkdir -p "$W/src" "$W/mv" "$W/plug/osirus/roms"
git archive v0.2.11 | tar -x -C "$W/src"
MVREV="$(git -C "$MV" rev-list -1 --before=2026-11-18T07:15Z HEAD)"     # the wrapper the release was built with
git -C "$MV" archive "$MVREV" wrapper tools | tar -x -C "$W/mv"
for f in "$ROMS"/*; do case "$f" in *Zone.Identifier) ;; *) ln -s "$f" "$W/plug/osirus/roms/";; esac; done
( cd "$W/src" && python3 ../mv/tools/gen_vst.py vst/vst.json --params-h >/dev/null )
cmake -S "$W/src" -B "$W/eng" -G Ninja -DCMAKE_BUILD_TYPE=Release -DMPC_VST="$(pwd)/$W/mv" >/dev/null
cmake --build "$W/eng" --target osirus_dsp -j"$(nproc)" >/dev/null
B="$W/eng"; libs=""
for l in libosirus_dsp.a virusLib/libvirusLib.a synthLib/libsynthLib.a baseLib/libbaseLib.a libresample/libresample.a \
         dsp56kEmu/libdsp56kEmu.a dsp56kBase/libdsp56kBase.a asmjit/libasmjit.a vtuneSdk/libvtuneSdk.a; do [ -f "$B/$l" ] && libs="$libs $B/$l"; done
gcc -O1 -g -fPIC -std=gnu11 -I"$W/src/vst/build" -I"$W/mv/wrapper" -c "$W/mv/wrapper/vst2_wrap.c" -o "$W/vst2_wrap.o"
g++ -shared -o "$W/plug/osirus.so" "$W/vst2_wrap.o" -Wl,--start-group $libs -Wl,--end-group -lpthread -lm -ldl
g++ -O1 -g -std=c++17 -o "$W/dump" tests/legacy_dump.cpp -ldl -lpthread
"$W/dump" "$W/plug/osirus.so" tests/data/legacy-0.2.11.chunk
