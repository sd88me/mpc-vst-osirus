# Osirus (Gen2): development notes (state as of 2026-10-23)

Repo `~/mpc-vst-osirus` (local git, nothing pushed). GPL-3.0, Gen2/aarch64 only. See README.md, src/VENDORED.md.

## State
- **Engine:** gearmulator Virus A/B/C (DSP56300 JIT) vendored in `src/gearmulator/`; schwung-virus glue `src/dsp/virus_plugin.cpp`
  (forked child -> in-process emulator thread); `src/dsp/mpc_engine.cpp` maps it to `wrapper/engine.h`.
- **Offline:** `./build.sh test` (x86 wrapper host test, PASSED); `build/x86/osirus_engine_test <dir with roms/>` passes for A, B, C
  (boot, notes, presets, bank/patch tiles, state chunk 4.8 KB). aarch64 probe under QEMU matches x86.
- **Device (user's MPC Live III, OS 3.9.1):** **0.1.7 is installed** (0.1.4 + STATS readout, B/C default DSP clock 100%) at `/nvme/Synths/sd88me - VST - Osirus/` (registered in
  `pluginList-arm-64bit`; MPC.settings backups beside it). User has confirmed it loads and makes sound (0.1.1). Not yet confirmed on the
  device: the latest skin (main page, BANKS tab, data wheel on presets, yellow Q-Link outlines, rom_bc hiding MOD 4-6 on a Virus A).
- **ROMs:** user's test zips (`dist-local/`, gitignored) carry their Virus A (`.mid` pair) and C (`.BIN`) ROMs from your own ROM folder
  (staged in the scratchpad `ex/roms`; recreate from your own ROM folder if gone). **Never commit or publish them.** The ROM folder is
  `<plugin folder>/osirus/roms/`; the engine picks the first by model (A before B before C).
- **Recipe to redeploy:** `./build.sh all`; `python3 ~/mpc-vst-plugins/tools/release.py --so vst/build/aarch64/osirus.so --skin "vst/build/skin/sd88me - VST - Osirus" --entry vst/build/pluginlist-entry.xml --version X --extra <dir with roms>:osirus --repo sd88me/mpc-vst-osirus --license GPL-3.0-only --id osirus -o dist-local`;
  unzip with `python3 -I -m zipfile -e`, tar over ssh to the Live III (`root@<live3-address>`, key login), `sh install.sh -y -t /nvme/Synths`.
  **Installing restarts MPC: ask first.** (A first attempt once printed "Job for acvs.service canceled" and changed nothing: run again.)
- **Live III screen/control:** `ssh -f -N -L 6721:127.0.0.1:6720 root@<live3-address>`, then `curl localhost:6721/screen.png?half=1`,
  `/tap?x=&y=`. No hardware buttons; the user adds the plugin to a track by hand. The `mpc` MCP points at the Force, not the Live III.
- **mpc-vst-plugins:** PRs #524 (`vs=0` knob option) and #525 (NOTES: filmstrip cache, Osirus CPU) are MERGED; the checkout is on `main`. (Old note: `skin-hide-knob-value` (a98315a: `vs=0` drops a knob's value text; the Osirus build NEEDS
  this branch checked out, or its `vs=0` knobs get a default value box; currently checked out) and `docs-osirus-gen2` (NOTES.md entries:
  MPC's filmstrip cache fills /var/volatile; first Osirus CPU reading). Open PRs for both when asked; docs for the Osirus port itself
  (GEN2.md, PORTING.md) are not written.

## Skin (done, awaiting the user's eyes on the device)
Galaxpel art (gearmulator `skins/Galaxpel`, by Emre Babus, GPL-3.0; Bebas Neue OFL) cropped per section at ONE scale (`S = 0.80`
in `tools/make_layout.py`, knob sockets 83 px everywhere), evenly packed by `pack()`, slate background, no knob values (`vs=0`),
Q-Links in blocks of four with `qlink_bounds=column` (yellow outlines; the `QL` table in make_layout.py).
Tabs: PLAY (title bar, preset/bank steppers, whole Patch Settings panel, ENGINE readouts + Panic, OUTPUT knobs), BANKS (bank list 1 col,
patches 3 cols x 10, page stepper), OSC, VOICE, FILTER, LFO 1+2, LFO 3 / ARP, MOD (slots 4-6 only with `rom_bc:Yes`), FX 1, FX 2, VELOCITY.
Commands: `tools/gen_params.py` -> `vst/params.json` (252 params; **append only**, params.lock), `tools/make_layout.py` -> `vst/layout.conf`,
`tools/preview.sh <name>` -> `vst/preview/<name>/page_N.png` (offline, no device), `tools/import_galaxpel.py` -> `skin/galaxpel/pages.json`.
Known skin gaps: Patch Settings "Secondary output" / "Out balance" are baked art with no parameter; FILTER page "Keyfollow base" shows as
a small knob; the header's baked ">" arrow; the value boxes of OUTPUT sit at the very bottom edge; velocity knobs appear on both FILTER and VELOCITY
(as in Galaxpel); B/C-only panels (OSC 3, phaser/EQ/dist, vocoder art) still show on a Virus A (only MOD 4-6 hides: add `when=rom_bc:Yes`
to those `pack()` pieces to hide more).

## Open items / next
1. **User test list** (ask the user for results): data wheel steps presets with the preset display focused; BANKS tiles light the current
   bank/patch and a tap loads it; page stepper; yellow Q-Link column outlines; MOD page in A mode (no slots 4-6); tab spacing/colour.
2. **CPU:** first reading ~59% of one core for the emulator thread on a Live III (probably Virus A at 100% clock). Test Virus B/C and the DSP
   CLOCK % control (B/C auto default is now 100%: at the old 35% a Virus C sounded distorted on the Live III, DSP thread ~57% of a fast core at 100%). `tools/bench.sh` is meaningless for this plugin (silent PASS): measure the
   emulator thread over SSH (`/proc/<pid>/task/<tid>/stat` deltas) while MPC plays it. Consider limiting JIT threads/cores, nice value (-5 emu, DSP thread -10 set by gearmulator).
3. **MPC filmstrip cache:** `/var/volatile/tmp/filmstrips` (tmpfs, never cleaned) filled to 100% and raised "Low Memory"; each MPC start writes ~260 files
   (~600 MB), each plugin load 42-128 files. Cleared by hand once (rm of all temp_*.img; nothing held them open). User asked for a permanent fix:
   plan = (a) test that MPC doesn't re-read deleted files while pages are used, (b) a small janitor addin (like skipback/commander) deleting stale
   `temp_*.img`, (c) fewer distinct knob strips per skin. Not started.
4. **Docs/catalog:** write Osirus entries in mpc-vst-plugins `docs/NOTES.md` (dated, device) / GEN2.md / PORTING.md (in-process emulator thread, aarch64-only,
   ROMs at runtime). Catalog: `catalog_build.py` has no aarch64-only plugin support yet; release needs `tested.json`, the release workflow, `catalog/plugins/osirus.json`.
5. **Engine gaps:** no MPC PRESET menu (`vst.json "programs": {"param": "preset"}`); the watchdog no longer respawns a hung emulator thread; B/C-only params
   still accept writes on an A ROM; `Out balance`/`Secondary output` unimplemented; user banks come from `osirus/banks/*.mid` (untested on the device).
6. Memory notes: `~/.claude/projects/-home-sam-mpc-vst-plugins/memory/osirus-gen2-port.md` (keep it in sync with this file).

## Update (later, 2026-10-23)
- User confirmed 0.1.7 "sounds good": the Virus C distortion was the DSP clock (old default 35% = Move number). Defaults are now 100% for A/B/C.
  Emulator thread ~56% of one fast core at 100% on a Virus C (Live III), DROPOUTS 0. Virus B at 100% untested.
- ENGINE panel STATS = `DROPOUTS n   DSP CPU x%` (emulator "DSP" thread CPU from /proc every ~2 s).
- Still open: data wheel / BANKS tile / Q-Link outline results not reported back; filmstrip-cache janitor; docs (GEN2/PORTING); catalog (aarch64-only);
  PRESET menu; hide more B/C-only panels on a Virus A with `when=rom_bc:Yes`.
