# Credits and licences

Osirus for MPC as a whole is distributed under the **GNU General Public License v3.0** (see `LICENSE`). It contains the work of others:

| What | Where | Who / licence |
|---|---|---|
| Virus emulation (virusLib, synthLib, baseLib) | `src/gearmulator/` | [gearmulator](https://github.com/dsp56300/gearmulator) by the dsp56300 project, GPL-3.0 (`src/gearmulator/LICENSE.md`). Vendored from the snapshot at [charlesvestal/gearmulator](https://github.com/charlesvestal/gearmulator), commit `c445e83` |
| DSP56300 emulator and JIT (dsp56kEmu, dsp56kBase) | `src/gearmulator/dsp56300/` | [dsp56300/dsp56300](https://github.com/dsp56300/dsp56300), GPL-3.0 (`LICENSE.md` there) |
| AsmJit | `src/gearmulator/dsp56300/asmjit/` | The AsmJit Authors, zlib licence (`LICENSE.md` there) |
| Intel ITT notify (vtuneSdk) | `src/gearmulator/dsp56300/vtuneSdk/` | Intel, GPL-2.0-only OR BSD-3-Clause (`LICENSE.*` there) |
| libresample | `src/gearmulator/libresample/` | Dominic Mazzoni (after resample-1.7 by Julius O. Smith), LGPL or BSD (`LICENSE-*.txt` there) |
| Plugin glue (`virus_plugin.cpp`, `program_selection.*`) | `src/dsp/` | [schwung-virus](https://github.com/charlesvestal/schwung-virus) by Charles Vestal, GPL-3.0; changed for MPC (see `src/VENDORED.md`) |
| Skin art: page backgrounds, knob filmstrip, header | `skin/galaxpel/`, derived `vst/images/` | The **"Galaxpel" skin by Emre Babus**, from gearmulator's Osirus plugin, GPL-3.0. Sections are cropped and scaled; controls are placed from its `.rml` |
| Font | `vst/fonts/` | Bebas Neue, SIL Open Font License 1.1 |
| Plugin wrapper (not in this repo) | `mpc-vst-plugins` | [sd88me/mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins); its Steinberg-SDK-free VST2 header layer |

The Virus ROMs (firmware and factory sounds) are copyrighted by their owner and are **not** part of this project: bring your own.
"Access", "Virus" and related names belong to Access Music GmbH; this project is not affiliated with or endorsed by them.
