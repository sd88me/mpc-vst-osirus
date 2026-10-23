#!/usr/bin/env python3
"""Runs on the built skin folder (vst.json "skin_post"): adds the MPC presets that start the plugin on a given ROM patch.
gen_vst.py writes Presets/0000-Default.xpl (empty state: the plugin's own start-up); this adds 0001-INIT.xpl, whose state is
the plugin's own saved-state JSON naming bank A, preset 126: the ROM's " - Init - " single on a Virus A, B and C alike."""
import os
import sys

for d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mpc-vst-plugins", "tools"),
          os.path.expanduser("~/mpc-vst-plugins/tools"), "/mv/tools"):
    if os.path.exists(os.path.join(d, "xpl.py")):
        sys.path.insert(0, d)
        break
import xpl  # noqa: E402

skin = sys.argv[1]
name, vendor, so = "Osirus", "sd88me", "osirus.so"
uid = int.from_bytes(b"OsrS", "big")
state = b'{"state_version":3,"bank":0,"preset":126}\0'
dst = os.path.join(skin, "Presets", "0001-INIT.xpl")
os.makedirs(os.path.dirname(dst), exist_ok=True)
so_path = "%%payload-path%%/%s - VST - %s/%s" % (vendor, name, so)
with open(dst, "w", encoding="utf-8") as f:
    f.write(xpl.xpl(name, vendor, so_path, uid, 1000, state, preset="INIT"))
print("preset:", dst)
