# Vendored source

- `gearmulator/` (baseLib, synthLib, libresample, virusLib, dsp56300/{dsp56kBase,dsp56kEmu,asmjit,vtuneSdk}): from
  https://github.com/charlesvestal/gearmulator commit `c445e8386c000a13a012b8de45b1ec105b979af7` (a snapshot of dsp56300/gearmulator),
  with its `source/dsp56300` submodule at `f8a4480165a0dba8a4ac9da4c0477ab829d198a6` (charlesvestal/dsp56300) and asmjit at
  `3577608cab0bc509f856ebf6e41b2f9d9f71acc4`. GPL-3.0, unmodified. Only the Virus subset is vendored (no JUCE, no Waldorf libraries).
- `dsp/virus_plugin.cpp`, `dsp/program_selection.*`: from https://github.com/charlesvestal/schwung-virus commit
  `26e1292a5a97314ed7660b493cee1b9782a5df1a` (GPL-3.0). Changes: the forked child process became an in-process emulator thread
  (state struct on the heap, per instance, user banks included); no signal handlers and no realtime policy for the whole process
  (only a nice value on the emulator thread); log only when `OSIRUS_LOG` names a file; bank/preset set before the boot finishes is
  remembered; `display_rev` key; numeric `rom_index`; the watchdog no longer respawns (a thread cannot be killed).
- `dsp/mpc_engine.cpp`: ours (the Schwung adapter's mapping onto `wrapper/engine.h`).
