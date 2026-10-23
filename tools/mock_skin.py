#!/usr/bin/env python3
"""Offline mock-ups of the same MPC pages cut from another of gearmulator's Osirus skins, to compare with the Galaxpel ones.
    mock_skin.py <skin dir with pages.json> <trancy|hoverland>     writes vst/mock/<name>/ (layout, skin, preview PNGs via tools/mock.sh)
Nothing here ships: the crop rectangles are per skin (measured from the page images)."""
import json
import os
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SKIN, NAME = os.path.abspath(sys.argv[1]), sys.argv[2]
OUT = os.path.join(HERE, "..", "vst", "mock", NAME)
os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
for f in ("params.json", "skin.css"):
    shutil.copy(os.path.join(HERE, "..", "vst", f), OUT)
shutil.copytree(os.path.join(HERE, "..", "vst", "fonts"), os.path.join(OUT, "fonts"), dirs_exist_ok=True)
shutil.copy(os.path.join(HERE, "..", "vst", "images", "knob_galaxpel.png"), os.path.join(OUT, "images"))
PARAMS = {p["key"]: p for p in json.load(open(os.path.join(OUT, "params.json")))["params"]}
PG = json.load(open(os.path.join(SKIN, "pages.json")))
Y86 = 86

CFG = {
    # page image per page id, scale so a ~socket is 83 px, and the crops: (page id, rect, x, y) per tab
    "trancy": dict(S=0.72, socket=115, bg="1b1b1d", panel="262626", accent="e04a3a", imgs={"page_osc": "panel_1.png", "page_lfo": "panel_2.png", "page_fx": "panel_3.png"},
        tabs={"OSC": [("page_osc", (0, 0, 970, 195)), ("page_osc", (0, 205, 970, 580))],
              "OSC 3 / UNISON": [("page_osc", (0, 595, 970, 790)), ("page_osc", (0, 802, 970, 995))],
              "FILTER": [("page_osc", (1367, 0, 2300, 575))],
              "ENV": [("page_osc", (1367, 595, 2300, 785)), ("page_osc", (1367, 802, 2300, 995))]}),
    "hoverland": dict(S=0.92, socket=90, bg="2a3350", panel="3b4668", accent="d9453a", imgs={"page_osc": "OSC_2034x1238_x2.png", "page_lfo": "LFO_2034x1238_x2.png", "page_fx": "FX_2034x1238_x2_D.png"},
        tabs={"OSC": [("page_osc", (44, 55, 802, 285)), ("page_osc", (44, 291, 802, 722))],
              "OSC 3 / UNISON": [("page_osc", (44, 730, 802, 960)), ("page_osc", (44, 965, 802, 1192))],
              "FILTER": [("page_osc", (1142, 55, 2032, 722))],
              "ENV": [("page_osc", (1142, 730, 2032, 960)), ("page_osc", (1142, 965, 2032, 1192))]}),
}[NAME]
S = CFG["S"]

lines = ["# mock-up from the %s skin (tools/mock_skin.py)" % NAME]
for k, v in {"bg": CFG["bg"], "panel": CFG["panel"], "line": "55586a", "ink": "e4e4e1", "ink_dim": "9aa0b0", "accent": CFG["accent"], "accent_hi": CFG["accent"],
             "knob_face": "202226", "knob_ring": "3a3d44", "knob_dot": CFG["accent"], "lcd": "1c1f22", "box": "1c1f22", "seg_active": CFG["accent"],
             "seg_inactive": "1c1f22", "seg_active_tx": "111216", "btn_bg": "202226", "btn_text": "e4e4e1", "btn_text_plain": "e4e4e1",
             "display_bg": "1c1f22", "display_cell": "232831", "display_off": "181b1f", "display_bezel": "0a0b0c", "display_ink": "ff8a7a"}.items():
    lines.append("theme_%s=%s" % (k, v))
lines += ["style=td3", "art_css=skin.css", "knob_strip=images/knob_galaxpel.png", "qlink_bounds=column"]
n = [0]


def piece(pid, rect, x, y):
    x0, y0, x1, y1 = rect
    n[0] += 1
    fn = "images/p_%d.png" % n[0]
    im = Image.open(os.path.join(SKIN, CFG["imgs"][pid])).convert("RGB").crop(rect)
    im = im.resize((int((x1 - x0) * S), int((y1 - y0) * S)), Image.LANCZOS)
    im.save(os.path.join(OUT, fn))
    lines.append('art x=%d y=%d w=%d h=%d file="%s"' % (x, y + Y86, im.width, im.height, fn))
    seen = set()
    for it in PG[pid]["items"]:
        cxp, cyp = it["x"] + it["w"] / 2, it["y"] + it["h"] / 2
        k = it["key"]
        if k in seen or not (x0 <= cxp < x1 and y0 <= cyp < y1) or (it["x"] == 0 and it["y"] == 0):
            continue
        seen.add(k)
        cx, cy = int(x + (cxp - x0) * S), int(y + (cyp - y0) * S) + Y86
        pr = PARAMS[k]
        if "options" in pr and (it["kind"] == "combo" or len(pr["options"]) > 2):
            lines.append('popup cx=%d cy=%d w=%d h=%d label="" key=%s' % (cx + int(6 * S), cy, max(int((it["w"] + 24) * S), 100), max(int((it["h"] + 8) * S), 36), k))
        elif "options" in pr:
            lines.append('toggle cx=%d cy=%d label="" key=%s ns=0' % (cx, cy, k))
        else:
            lines.append('knob cx=%d cy=%d r=%d label="" key=%s ns=0 vs=0 bw=%d' % (cx, cy, int(CFG["socket"] * S / 2) - 2, k, int(CFG["socket"] * S)))
    return im.size


for tab, pieces in CFG["tabs"].items():
    lines += ["", "[tab %s]" % tab]
    sizes = [(Image.open(os.path.join(SKIN, CFG["imgs"][p])).crop(r).size) for p, r in pieces]
    hs = [int(h * S) for _, h in sizes]
    gap = max(10, (628 - sum(hs)) // (len(pieces) + 1))
    y = (628 - sum(hs) - gap * (len(pieces) - 1)) // 2
    for (pid, rect), (w, h) in zip(pieces, sizes):
        piece(pid, rect, (1280 - int(w * S)) // 2, y)
        y += int(h * S) + gap
open(os.path.join(OUT, "layout.conf"), "w").write("\n".join(lines) + "\n")
v = json.load(open(os.path.join(HERE, "..", "vst", "vst.json")))
v.update(name="Osirus Mock", layout="layout.conf", build={"root": "../../..", "sources": [], "cflags": [], "libs": ["-lm"]})
for k in ("tile", "skin_post", "targets", "so"):
    v.pop(k, None)
v["so"] = "osirus.so"
v["targets"] = ["aarch64"]
json.dump(v, open(os.path.join(OUT, "vst.json"), "w"), indent=2)
print(OUT)
