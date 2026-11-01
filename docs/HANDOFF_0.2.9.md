# Handoff: roll the open Osirus changes into one release (0.2.9), build against current wrapper tools (state as of 2026-11-01)

Everything below is **local** in `~/mpc-vst-osirus` unless it says otherwise. 0.2.8 is released and in the catalog. Nothing in this note is released.

## Branches (all local, nothing pushed)

| Branch | What | Tested |
|---|---|---|
| `main` (= `origin/main`, `1224411`) | 0.2.8: every MIDI channel plays, GAIN % renamed OUTPUT LEVEL %, DSP clock max 100, README on clipping. Pushed, released (v0.2.8). | yes, on the Live III |
| `headroom` (`1bbe379`, from main) | the crackle fix: Virus channel volume (CC 7) held at 100, `HEADROOM_MAKEUP` 1.9 after it, `soft_limit()` in the resampler, a controller's CC 7 scaled into 0..100. No new control. | offline (Virus C and A), then on the Live III: "sounds better" |
| `favourites` (`0ba4219`, from main) | `+FAV` / `-FAV` buttons on BANKS, `favourites.dat` in `<module_dir>`, native MPC PRESET menu via vst.json `"programs": {"param": "favourite"}`, model tag per favourite, `test/soak.cpp` | on the Live III: buttons appear, favourites listed and picked correctly, names refresh immediately, menu no longer re-pops, opens near the favourites |
| `test-build` (`4283e4e`) | `favourites` + `headroom` merged. This is what is on the Live III (md5 `cca32e79...`). Not for release as a branch: merge the two into `main` instead. | as above |
| `old-main` | an old history that diverged from `main` (19 commits `main` lacks). Left alone. Do not merge blindly. | n/a |

## Do this

1. **Wrapper tools up to date.** `~/mpc-vst-plugins` is a dirty checkout on `install-page-overhaul` (someone's uncommitted change), so do not build with it. Its `tools/html_art.py` also lacks `boxbtn`, so the skin build fails once a button has `w=`/`h=`.
   Use a clean checkout of mpc-vst-plugins `origin/main`: `git -C ~/mpc-vst-plugins-main fetch && git -C ~/mpc-vst-plugins-main checkout --detach origin/main` (that worktree was at `130f5e8`, older), then `MPC_VST=$HOME/mpc-vst-plugins-main ./build.sh all`.
   The `rom-upload-helper` worktree (`~/mpc-vst-plugins-rom`) was deleted from disk. **Its branch is merged** (PR #668, 2026-10-31): `release.py --user-files`, `user_files.py` and the installer's "Your ROMs and files" step are in `origin/main`. The old note HANDOFF_ROM_UPLOAD.md saying "local only, release.sh needs the branch" is out of date: update it.
2. **Merge into `main`:** `git checkout main && git merge headroom && git merge favourites` (both edit `src/dsp/virus_plugin.cpp` in different places; the merge in `test-build` was clean). Drop `test-build`.
3. **Add `.syx` support** to `child_load_user_banks` (`src/dsp/virus_plugin.cpp`, the `.mid` extension test): accept `.syx` too. The loader already handles raw SysEx (`MidiToSysex::extractSysexFromData` treats a file with no `MThd` header as SysEx). Verified offline that a real 128-single Virus bank (`Electro_Transform.syx`, 34176 bytes, 128 x 267) loads as 128 patches when renamed `.mid`. Update the README ("`.mid` or `.syx`").
4. **Optional small change:** the STATS CPU figure only moves on a 15 point shift (`inst->stats_cpu`); 10 is probably better (the 15 s freeze after the program menu is listed does the real work).
5. **README + release notes** for: favourites, headroom (OUTPUT LEVEL keeps its meaning; at moderate velocity the level is within 0.5 dB of before), `.syx`. Do not mention the 3.10.1 layout anywhere public (it is not public yet; see below).
6. **Build, deploy, test** (see "Device" below), then `MPC_VST=<clean worktree> ./release.sh 0.2.9`, `catalog_check`, `git tag v0.2.9`, push, `gh release create`, then trigger the catalog (`gh workflow run catalog.yml -R sd88me/mpc-vst-plugins`, ~8 min, or wait for the nightly 03:17 UTC) and confirm the live `catalog.json` shows 0.2.9. **Ask before each public step.**
7. **`tested.json`:** 0.2.8 has no entry (its only test was on 3.10.1; the user does not want 3.10.1 recorded). 0.2.9 needs a 3.9.x test, or the user's decision to leave it out. The catalog still lists a release without one (tier "listed").

## What was found (do not redo)

- **Keyboard silent on channel 2+:** `Microcontroller::sendMIDI` drops channel messages not on the global channel (0, single mode). Fixed in `child_send_midi` (channel forced to 1). Confirmed fixed on the Live III.
- **Crackle:** not underruns, not the DSP clock. The emulated Virus clips its own output stage (peak 1.000, 230+ flat tops per 3 min of chords); GAIN acts after it. Capture method: a temporary build dumping the resampled int16 stream plus the `[child] blk= buf= ur= peak=` log lines (`OSIRUS_LOG`); `/etc` on the device is read-only, so env vars cannot be set there (a marker file in `/nvme` was used and removed). CC 7 acts before the clip: clipped samples 46106 (127), 824 (100), 6 (80), 0 (64); level ~ (cc/127)^2.1..2.9; Virus A: CC 64 gave -12.9 dB.
- **A second crackle pattern is open (user 1):** "starts fine, gets worse as patches change, DROPOUTS above 0 in their screenshots, MPC 3.9.0". A real-time soak (`test/soak.cpp`, patch change each second, held chord) on the Live III and the PC showed no drift (memory, threads, DSP CPU flat); 3 dropouts in the first 12 s on the device (cold JIT), none after. **Waiting for their answers:** does DROPOUTS climb steadily or in bursts; does reloading only the plugin clear it; tracks/plugins, buffer size; 3.9.0 vs 3.9.1. A deeper ring (`RING_TARGET_FILL` 768 -> ~1800) is a candidate for the cold-start dropouts, not yet built.
- **Native preset picker:** `Presets/*.xpl` in the plugin folder does NOT feed it on the Live III (3.10.1 layout): neither `INIT` nor `Default` listed, a test `0002-Test.xpl` did not appear. What works is the wrapper's **VST programs** (`effGetProgramNameIndexed`), as JN-106 uses. With `"programs": {"param": "favourite"}` the wrapper takes the names from `get_param("favourite:<n>")`; the count (64) is fixed at load, names refresh live. Not verified on 3.9.x.
- **Program-menu behaviour in MPC:** every `audioMasterUpdateDisplay` makes MPC re-list the programs and close the popup. The STATS text (CPU % changes every ~2 s) caused it: held still for 15 s after any `favourite:<n>` query, CPU shown only on a 15 point change. The wrapper ignores re-picking the current program, so `get_param("favourite")` reports the first EMPTY slot when the current patch is not a picked favourite (the menu then opens beside the favourites; reporting the last slot made it open at the bottom).
- **Favourites and ROMs:** a favourite holds the whole 512-byte single plus the model letter (name byte 31: A/B/C; 0 = an old file, loads anywhere). Listed as `Name [C]` on a matching ROM, `Name <C>` on another (not loaded: a single from another model underran a Virus A). It does not record the ROM file or number. **Not tested on the device yet:** switching between an A and a C ROM with favourites saved on each; the `-FAV` delete; the limiter on loud material by ear; headroom on a Virus A by ear.
- **Catalog:** versions are discovered from GitHub Releases by a nightly job (03:17 UTC); 0.2.8 only appeared after a manual `workflow_dispatch`.

## Device (user's MPC Live III, 192.168.2.217, key login as root)

- Runs MPC OS **3.10.1** (not public: no public mention). Plugins load from `/nvme/VST2 Plugins/<Mfr> - VST - <Name>/`; the old `/nvme/Synths/...` copy and its `MPC.settings` entry remain, and the user saw the skin from there too, so **keep both folders in step** (`osirus.so` and `Plugin Skins/`). A swap of `osirus.so` alone leaves the old skin. Stage a copy and `mv` it into place; clear `/var/volatile/tmp/filmstrips/temp_*.img`; `systemctl restart acvs` (this restarts MPC: ask first).
- Currently installed: `test-build` (md5 `cca32e79c67e391a1f9efc12570270c8`).
- Leftovers to delete when done: `/nvme/osirus-0.2.7.so.bak`, `/nvme/osirus-skin-0.2.7.bak`, `/nvme/osirus-synths-skin-old.bak`. Keep `/nvme/osirus-roms-backup` (the user's ROMs: never commit or publish them; a copy for offline tests was put in the scratchpad `data/roms`, gone with the session).
- The screen/MIDI remote (port 6720) is NOT running on this device; the `mpc` MCP points at the Force. Ask the user to look at the screen.

## Pitfalls

- The skin tool splits button labels on spaces: `"SAVE FAV"` crashed `html_art`; use `+FAV`.
- `vst/params.lock` is append-only; new params (`favourite`, `fav_save`, `fav_delete`) are already appended last. `vst/layout.conf` is generated and tracked: commit it.
- `./build.sh test` needs `python3 tools/make_custom.py --install` first (build.sh does it). The x86 soak: add `test/soak.cpp` to CMake (`add_executable(osirus_soak test/soak.cpp)` + `target_link_libraries(... osirus_dsp)`; it is in `favourites`).
- Every release also changes the zip's skin: tell users a restart may be needed to see changed labels (MPC caches skin pictures).

## Draft note for users (after the release is up)

0.2.9: headroom (the crackle on heavy chords: Osirus now keeps the Virus out of its own clipping, no new control), favourites (+FAV / -FAV on the BANKS page; they show in MPC's PRESET menu), `.syx` banks in `osirus/banks/`. If crackle persists: patch name, MPC model and OS version, buffer size, the STATS line (DROPOUTS n), and whether it grows as you change patches.
