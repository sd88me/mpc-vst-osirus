#!/usr/bin/env bash
# Build Osirus. The engine (gearmulator's Virus emulation + src/dsp glue) is built with CMake into one static archive,
# vst/build/engine/libosirus_all.a, which vst/vst.json links into the plugin through tools/build_port.sh.
#   ./build.sh engine [x86|aarch64]   just the archive for that architecture (default aarch64, cross-compiled in Docker)
#   ./build.sh test                   x86 engine + the offline host test (tools/test_port.sh, ASan/UBSan)
#   ./build.sh [all]                  aarch64 engine + skin + osirus.so in vst/build/aarch64/ (Gen2)
# MPC_VST: checkout of mpc-vst-plugins (default ~/mpc-vst-plugins).
set -euo pipefail
cd "$(dirname "$0")"
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins}"
IMAGE=osirus-a64-builder

merge() {   # merge <ar> <build dir>
  local AR="$1" B="$2" out="vst/build/engine/libosirus_all.a"
  mkdir -p vst/build/engine
  { echo "CREATE $out"
    for l in libosirus_dsp.a virusLib/libvirusLib.a synthLib/libsynthLib.a baseLib/libbaseLib.a libresample/libresample.a \
             dsp56kEmu/libdsp56kEmu.a dsp56kBase/libdsp56kBase.a asmjit/libasmjit.a vtuneSdk/libvtuneSdk.a; do
      [ -f "$B/$l" ] || { echo "missing $B/$l" >&2; exit 1; }
      echo "ADDLIB $B/$l"
    done
    echo "SAVE"; echo "END"; } | $AR -M
  echo "engine archive: $out ($(du -h $out | cut -f1))"
}

engine() {
  case "${1:-aarch64}" in
    x86)
      cmake -S . -B build/x86 -G Ninja -DCMAKE_BUILD_TYPE=Release -DMPC_VST="$MPC_VST" >/dev/null
      cmake --build build/x86 --target osirus_dsp -j"$(nproc)"
      merge ar build/x86 ;;
    aarch64)
      docker image inspect $IMAGE >/dev/null 2>&1 || docker build -q -t $IMAGE -f scripts/Dockerfile scripts
      docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/b -v "$MPC_VST":/mv:ro -w /b $IMAGE bash -euc '
        cmake -S . -B build/a64 -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/aarch64-toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DMPC_VST=/mv >/dev/null
        cmake --build build/a64 --target osirus_dsp -j"$(nproc)"'
      merge "docker run --rm -i -u $(id -u):$(id -g) -v $PWD:/b -w /b $IMAGE aarch64-linux-gnu-ar" build/a64 ;;
    *) echo "unknown arch $1" >&2; exit 1 ;;
  esac
}

case "${1:-all}" in
  engine) engine "${2:-aarch64}" ;;
  test)   python3 tools/gen_params.py; python3 tools/make_custom.py --install; engine x86; "$MPC_VST/tools/test_port.sh" vst/vst.json ;;
  all)    python3 tools/gen_params.py; python3 tools/make_custom.py --install; engine aarch64; "$MPC_VST/tools/build_port.sh" vst/vst.json aarch64 ;;
  *) sed -n 2,9p "$0"; exit 1 ;;
esac
