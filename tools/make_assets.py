#!/usr/bin/env python3
"""Regenerate the two committed images that come from the Galaxpel skin art (skin/galaxpel/):
  vst/images/knob_galaxpel.png  the knob filmstrip (181 source frames resampled to 101, 104 px each)
  vst/images/tile.png           the 270x110 Instruments-browser tile (the OSIRUS logo from main_bg.png)
The page crops (vst/images/gp_*.png, galaxpel_page_*.png) are written by tools/make_layout.py and are not committed."""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "..", "skin", "galaxpel")
OUT = os.path.join(HERE, "..", "vst", "images")
os.makedirs(OUT, exist_ok=True)

# knob strip: the original knob_2-104x104.png is 181 frames; MPC wants <= 16384 px and resamples to its own count
src = os.path.join(SK, "knob_2-104x104.png")
if os.path.exists(src):
    im = Image.open(src).convert("RGBA")
    n = im.height // 104
    out = Image.new("RGBA", (104, 104 * 101))
    for i in range(101):
        f = i * (n - 1) // 100
        out.paste(im.crop((0, f * 104, 104, f * 104 + 104)), (0, i * 104))
    out.save(os.path.join(OUT, "knob_galaxpel.png"))
else:
    print("skin/galaxpel/knob_2-104x104.png not here: keeping the committed knob_galaxpel.png")

im = Image.open(os.path.join(SK, "main_bg.png")).convert("RGB")
logo = im.crop((150, 60, 490, 200))
t = Image.new("RGB", (270, 110), im.getpixel((60, 230)))
s = min(250 / logo.width, 100 / logo.height)
l = logo.resize((int(logo.width * s), int(logo.height * s)), Image.LANCZOS)
t.paste(l, ((270 - l.width) // 2, (110 - l.height) // 2))
t.save(os.path.join(OUT, "tile.png"))
print("tile.png, knob_galaxpel.png")
