# Osirus (Gen2): development notes (state as of 2026-10-23)

Repo `~/mpc-vst-osirus` (local git, nothing pushed). GPL-3.0, Gen2/aarch64 only. See README.md, src/VENDORED.md.

## 0.2.8 (2026-10-31): user reports, what was found
- **Keyboard on another MIDI channel was silent** (pads, channel 1, played): `Microcontroller::sendMIDI` drops channel messages whose channel is not the global one (0,
  single mode). Fixed in `child_send_midi` (channel forced to 1: the track is the routing). Verified on the Live III.
- **"Crackle", DROPOUTS 0, worse with high-velocity heavy chords, DSP CLOCK / GAIN do not help:** it is the Virus's own output clipping (the emulator's float output
  reaches 1.000; ~230 flat-topped runs in 3 minutes of playing; no underruns, no slow blocks, no dropped blocks, DSP thread ~57% of one core, machine ~89% idle).
  GAIN is applied after the clip, so it cannot help; **PATCH VOLUME** (inside the Virus) does. The DSP clock cap was raised to 200 as an experiment: no effect, reverted (max 100).
  GAIN % was renamed OUTPUT LEVEL % (key `gain` unchanged, so saved states load). Possible follow-up: a headroom setting that lowers the patch volume inside the Virus.
- **How it was measured (no env on the device: /etc is read-only):** a temporary build dumped the resampled int16 stream to a file and logged per-block times (`[child] blk= buf= ur= peak=`
  every ~2 s already exists with `OSIRUS_LOG`); the dump was scanned for flat tops and 2nd-difference spikes. Removed again before the release. Repeat the same way if a report shows DROPOUTS above 0.
- **Releasing:** `MPC_VST=<worktree of mpc-vst-plugins on rom-upload-helper> ./release.sh <version>` (see HANDOFF_ROM_UPLOAD.md; that branch is still local). 0.2.8 is released and in `tested.json`.

## State (2026-10-25)
- **Repo:** https://github.com/sd88me/mpc-vst-osirus (public, GPL-3.0; README, CREDITS.md, src/VENDORED.md). `main` is pushed.
- **Engine:** gearmulator Virus A/B/C (DSP56300 JIT) vendored in `src/gearmulator/`; schwung-virus glue `src/dsp/virus_plugin.cpp`
  (forked child -> in-process emulator thread); `src/dsp/mpc_engine.cpp` maps it to `wrapper/engine.h`. B/C default DSP clock is 100%
  (the Move's 45%/35% distorted a Virus C on the Live III). 254+ parameters (append only, `vst/params.lock`).
- **Offline:** `./build.sh test` (x86 wrapper host test, PASSED); `build/x86/osirus_engine_test <dir with roms/>` passes for A, B, C
  (boot, notes, presets, bank/patch tiles, INIT, state chunk). aarch64 probe under QEMU matches x86.
- **Device (user's MPC Live III, OS 3.9.1):** **0.1.9 is installed** at `/nvme/Synths/sd88me - VST - Osirus/` (registered in
  `pluginList-arm-64bit`; MPC.settings backups beside it), loaded for the user to test (OSC+VOICE merged page, taller header steppers).
  Confirmed by the user earlier: loads, sounds, banks and tile steppers OK, Virus C distortion fixed by the 100% clock.
  Not yet reported: data wheel stepping presets, Q-Link column outlines on every page, the merged OSC page, MOD page on a Virus A.
- **ROMs:** user's test zips (`dist-local/`, gitignored) carry their Virus A (`.mid` pair) and C (`.BIN`) ROMs, staged in the scratchpad
  `ex/roms` (copy again from the user's own ROM folder if gone). **Never commit or publish them.** ROM folder on the device:
  `<plugin folder>/osirus/roms/`; the engine picks the first by model (A before B before C); ROM NUMBER on PLAY selects.
- **Redeploy recipe:** `./build.sh all`; `python3 ~/mpc-vst-plugins/tools/release.py --so vst/build/aarch64/osirus.so --skin "vst/build/skin/sd88me - VST - Osirus" --entry vst/build/pluginlist-entry.xml --version X --extra <dir with roms>:osirus --repo sd88me/mpc-vst-osirus --license GPL-3.0-only --id osirus -o dist-local`;
  unzip with `python3 -I -m zipfile -e`, tar over ssh to the Live III (`root@<live3-address>`, key login), `sh install.sh -y -t /nvme/Synths`.
  **Installing restarts MPC: ask first.** (Once it printed "Job for acvs.service canceled" and changed nothing: run again.) The osirus build needs
  mpc-vst-plugins on `main` at or after PR #524 (`vs=0`).
- **Live III screen/control:** `ssh -f -N -L 6721:127.0.0.1:6720 root@<live3-address>`, then `curl localhost:6721/screen.png?half=1`, `/tap?x=&y=`,
  `/down` `/move` `/up` for a drag. No hardware buttons; the user adds the plugin to a track. The `mpc` MCP points at the Force, not the Live III.
- **mpc-vst-plugins:** merged #524 (`vs=0`), #525 (NOTES: filmstrip cache, Osirus CPU), #528 (catalog: a Gen2-ONLY plugin via
  `asset_pattern: "*-mpc-aarch64.zip"`, `gen2_only`). **#529 (gofmt of tools/desktop/catalog.go, the Desktop installer CI was red after #528) is open.**

- **ROM upload step for the desktop installer:** built, tested offline, not pushed or tried on the device: see docs/HANDOFF_ROM_UPLOAD.md.

## Skin
Galaxpel art (gearmulator `skins/Galaxpel`, by Emre Babus, GPL-3.0; Bebas Neue OFL) cropped per section, evenly packed (`pack()`), slate
background, no knob values (`vs=0`), Q-Links in blocks of four with `qlink_bounds=column` (`QL` table in `tools/make_layout.py`).
Scale: `S = 0.80` everywhere (knob sockets 83 px) EXCEPT the merged OSC page, drawn at 0.67 (70 px) so oscillators 1-3, mixer, ring mod, sub,
unison and portamento fit one page. Tabs: PLAY (title bar + preset/bank steppers covering the baked display bar, whole Patch Settings panel,
ENGINE: ROM/STATUS/STATS + PANIC + INIT PATCH, OUTPUT knobs), BANKS (bank list 1 column, patches 3 x 10, page stepper), OSC, FILTER, LFO 1+2,
LFO 3 / ARP, MOD (slots 4-6 only with `rom_bc:Yes`), FX 1 (dist, analog, phaser, chorus), FX 2 (EQ, punch, delay), VELOCITY.
Commands: `tools/gen_params.py` -> `vst/params.json`; `tools/make_layout.py` -> `vst/layout.conf`; `tools/preview.sh <name>` ->
`vst/preview/<name>/page_N.png` (offline, no device); `tools/import_galaxpel.py [skin dir rml desc]` -> `pages.json` (any of the Osirus
skins); `tools/make_assets.py` -> knob strip + browser tile; `tools/mock_skin.py` draws Trancy/Hoverland comparison pages (not shipped).
User decision: **stay with Galaxpel** (Trancy = dark, clean sections but small labels; Hoverland = Galaxpel-like, largest labels).
Known skin gaps: Patch Settings "Secondary output" / "Out balance" are baked art with no parameter; FILTER "Keyfollow base" and the arpeggiator
"pattern" are knobs in dropdown sockets (no option list); the SYNC toggle covers the end of "SYNC 2-1"; MOD leans left on a Virus A; B/C-only panels
(OSC 3, phaser/EQ/dist, vocoder art) still show on a Virus A (add `when=rom_bc:Yes` to those `pack()`/`piece()` calls to hide); the header's baked arrow.
PRESETS: `Presets/0000-Default.xpl` and `0001-INIT.xpl` (the ROM's " - Init - " single, bank A preset 126) + browser tile, via `vst/skin_post.py`.

## Open items / next
1. **User test list** (ask for results): data wheel on presets (focus the preset display first), BANKS tiles, Q-Link outlines, merged OSC page, MOD on A.
2. **Catalog entry:** merge #529 (optional), then: ROM-FREE release zip (`release.py ... --extra` with NO roms, or none), tag, GitHub release (public action: ask),
   `catalog_check.py <zip> --catalog --expect-id osirus --expect-repo sd88me/mpc-vst-osirus`, `tested.json` in the Osirus repo (MPC Live III (Gen2), 3.9.1,
   version, date), then a PR adding `catalog/plugins/osirus.json` (`"asset_pattern": "*-mpc-aarch64.zip"`, style synth, tags emulation/virus, license GPL-3.0-only,
   https screenshot, summary that does not imply Access endorsement). Also needs the Osirus `vst-release.yml` workflow or a manual `gh release create`.
3. **CPU:** Virus C at 100% ~56% of one fast core, DROPOUTS 0 (STATS readout `DROPOUTS n   DSP CPU x%`). Virus B at 100% untested. `tools/bench.sh` is
   meaningless for this plugin (silent PASS): measure the "DSP" thread over SSH (`/proc/<pid>/task/<tid>/stat` deltas).
4. **MPC filmstrip cache:** `/var/volatile/tmp/filmstrips` (tmpfs, never cleaned) fills (~1 GB per MPC restart + plugin load; this session's reinstalls caused it) and raises
   "Low Memory"; clear with `rm /var/volatile/tmp/filmstrips/temp_*.img` (nothing holds them open). Janitor addin / fewer knob strips: not started (NOTES.md has the facts).
5. **Docs:** mpc-vst-plugins GEN2.md / PORTING.md entries for the Osirus port (in-process emulator thread, aarch64-only, ROMs at runtime) not written.
6. **Engine gaps:** no MPC PRESET-menu list of the ROM's own patches (`vst.json "programs"`); watchdog no longer respawns a hung emulator thread; B/C-only params accept writes
   on an A ROM; Out balance / Secondary output unimplemented; `osirus/banks/*.mid` user banks untested on the device.
7. Memory notes: `~/.claude/projects/-home-sam-mpc-vst-plugins/memory/osirus-gen2-port.md` (keep in sync with this file).
