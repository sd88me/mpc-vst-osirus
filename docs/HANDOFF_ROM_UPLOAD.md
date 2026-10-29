# Handoff: the installer's ROM upload step (state as of 2026-10-29)

Picks up after the other installer releases are out. Nothing here is pushed or released yet.

## What exists

- **mpc-vst-plugins, branch `rom-upload-helper`, commit `21d8845`** (local only; based on `origin/main` at `df4ce22`). It was made in a git worktree under
  the Claude scratchpad, which may be gone: the commit lives in `~/mpc-vst-plugins/.git`, so `git worktree prune` then
  `git worktree add <dir> rom-upload-helper`, and rebase onto the current `origin/main` before using it. Do NOT build in `~/mpc-vst-plugins` itself
  while it sits on `install-page-overhaul` with someone's uncommitted change (`docs/handoff-wrapper-fix/...` shows as deleted there).
  - `tools/desktop/userfiles.go`: rules (`UserFileGroup`/`UserFileRule`), `Validate`, device listing, upload, delete; routes `/api/userfiles`,
    `/api/userfiles/upload`, `/api/userfiles/delete`. `Manifest`/`CatPlugin`/`knownPlugin` carry `UserFiles`.
  - `tools/desktop/web/index.html`: new step 4 "Your ROMs and files" (later steps renumbered 5 to 8), shown only when a plugin on the device declares files.
  - `tools/user_files.py` (shared check), `release.py --user-files <json>`, `catalog_check.py` validation, `tools/test_user_files.py`,
    `tools/desktop/userfiles_test.go`, docs in `docs/CATALOG_SPEC.md` and `tools/desktop/README.md`.
- **mpc-vst-osirus, `main`, commit `c6eb5f2`** (local; 0.2.7 itself is pushed and released): `release/userfiles.json` (the Osirus rules) and `release.sh`
  passing `--user-files release/userfiles.json`. **`release.sh` needs mpc-vst-plugins with the branch above**; until it is merged, build with
  `MPC_VST=<worktree> ./release.sh <version>`, and do not release from a checkout without it (the flag would be an unknown argument).

## Tested (offline)

Full `go test -race ./...` in tools/desktop (docker `golang:1.26`; `go build` overwrites the tracked binary `tools/desktop/desktop`: `git checkout` it);
`python3 tools/test_catalog.py` (138 OK); a real-browser run of the new step with mocked API responses (playwright docker image
`mcr.microsoft.com/playwright/python:v1.47.0-jammy`, `pip install playwright==1.47.0` inside; the page opens on the USB-stick tab, click `#mode-install` first);
a throwaway Osirus 0.2.8 build with the spec in its manifest passed `catalog_check`.

## Not done

1. **Not tried against the real Live III** (192.168.2.217, key login as root). Build the installer from the branch, connect, upload a ROM to
   `<Synths>/sd88me - VST - Osirus/osirus/roms/`, check the list and a delete. Back up the ROMs first (a copy is in `/nvme/osirus-roms-backup`).
2. **The repo's own browser tests** (`tools/desktop/ui_test`) were not run; the step has no case there. Add one.
3. **The catalog only gets `user_files` from the next Osirus release built with the branch.** Cut it (0.2.8, new `tested.json` entry, notes) after the PR merges;
   check the catalog build and `catalog_site` accept the new manifest field.
4. **PR for mpc-vst-plugins**: not opened (public repo; ask first). Docs sync is done (CATALOG_SPEC, desktop README); the PR template asks about NOTES.md:
   add the Live III result there once step 1 is verified.
5. **Known limits:** a Virus A ROM is a `.mid` pair; only size and the `MThd` header can be checked (shown as "Looks right", the plugin decides on load);
   the rules in `release/userfiles.json` mirror the plugin's detection (`ROMLoader::detectModel`), and `osirus_romcheck` (`test/romcheck.cpp`) is the
   authority if they ever disagree. Not offered: renaming files, other synths' specs (Schwung's JV-880 is the model: size + CRC32 per file).

## Why

Beginners fail at "put the ROM in `osirus/roms/`". Schwung's manager does a per-file table with size/CRC checks; this is the MPC installer's version.
Related fixes shipped in 0.2.7: upgrades kept the user's ROMs only after `release.sh` passed `--user-data osirus/roms` and `osirus/banks` (it did not before, and
an upgrade wiped the ROMs); ROM # now restarts the emulator once, after it settles (a per-step restart crashed Ableton Live).
