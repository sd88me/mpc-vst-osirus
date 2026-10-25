#!/usr/bin/env python3
"""A custom MPC layout in the Galaxpel look (vst/custom/): every page is drawn here (PIL) at the MPC's 1280 x 628, from Galaxpel's own
pieces (Bebas Neue, the section icons skin/parts/icon_*.png, the knob socket skin/parts/socket.png, the knob filmstrip) and
laid out for the MPC instead of cropped from Galaxpel's pages. The live controls go over the drawn sockets.
    make_custom.py       writes vst/custom/layout.conf, images/ and vst.json
Colours and sizes are the constants below."""
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "vst", "custom")
PARTS = os.path.join(ROOT, "skin", "parts")
FONT = os.path.join(ROOT, "vst", "fonts")
Y86 = 86
W, H = 1280, 628

BG = (34, 39, 51)           # page
PANEL = (58, 64, 79)        # Galaxpel's panel slate (the socket art's own background)
PANEL_HI = (68, 75, 92)
PANEL_LO = (44, 49, 61)
EDGE = (24, 27, 36)
TAB = (62, 68, 84)
INK = (209, 214, 228)
INK_DIM = (140, 148, 168)
INSET = (46, 51, 64)
SOCK = 84                   # knob socket size on screen: 104 px art scaled down

os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
for f in ("params.json", "skin.css"):
    shutil.copy(os.path.join(ROOT, "vst", f), OUT)
shutil.copytree(FONT, os.path.join(OUT, "fonts"), dirs_exist_ok=True)
shutil.copy(os.path.join(ROOT, "vst", "images", "knob_galaxpel.png"), os.path.join(OUT, "images"))
PARAMS = {p["key"]: p for p in json.load(open(os.path.join(OUT, "params.json")))["params"]}

F = lambda size, bold=False: ImageFont.truetype(os.path.join(FONT, "BebasNeue-%s.ttf" % ("Bold" if bold else "Regular")), size)
_sock = Image.open(os.path.join(PARTS, "socket.png")).convert("RGB")
_bgc = _sock.getpixel((1, 1))
_a = Image.eval(Image.merge("L", [Image.new("L", _sock.size, 0)]), lambda v: v)
_a = _sock.point(lambda v: v).convert("L")
SOCKET = _sock.resize((SOCK, SOCK), Image.LANCZOS).convert("RGBA")   # the art's flat panel colour becomes transparent, the rim and the shadow stay
_px = SOCKET.load()
for _y in range(SOCK):
    for _x in range(SOCK):
        _r, _g, _b, _ = _px[_x, _y]
        _d = abs(_r - _bgc[0]) + abs(_g - _bgc[1]) + abs(_b - _bgc[2])
        _px[_x, _y] = (_r, _g, _b, max(0, min(255, _d * 40)))
ICON = {}


def icon(name):
    if name not in ICON:
        ICON[name] = Image.open(os.path.join(PARTS, "icon_%s.png" % name)).convert("RGBA")
    return ICON[name]


lines = []
emit = lines.append


class Page:
    def __init__(self, name, qkeys):
        self.name, self.qkeys = name, qkeys
        self.im = Image.new("RGB", (W, H), BG)
        self.d = ImageDraw.Draw(self.im)
        self.widgets = []

    # ---- drawing
    def text(self, x, y, s, size=22, color=INK, bold=False, anchor="la"):
        self.d.text((x, y), s, font=F(size, bold), fill=color, anchor=anchor)

    def panel(self, x, y, w, h, title="", ico=None):
        d = self.d
        d.rounded_rectangle((x, y, x + w, y + h), 6, fill=PANEL, outline=EDGE, width=2)
        d.line((x + 3, y + 3, x + w - 3, y + 3), fill=PANEL_HI)
        d.line((x + 3, y + h - 3, x + w - 3, y + h - 3), fill=PANEL_LO)
        if title:
            tw = int(F(27, True).getlength(title)) + (int(icon(ico).width * 0.78) + 12 if ico else 0) + 28
            d.rounded_rectangle((x, y, x + tw, y + 34), 5, fill=TAB, outline=EDGE, width=2)
            d.line((x + 3, y + 33, x + tw - 3, y + 33), fill=EDGE)
            self.text(x + 14, y + 4, title, 27, INK, True)
            if ico:
                ic = icon(ico)
                self.im.paste(ic.resize((int(ic.width * 0.78), int(ic.height * 0.78)), Image.LANCZOS), (x + tw - 10 - int(ic.width * 0.78), y + 6),
                              ic.resize((int(ic.width * 0.78), int(ic.height * 0.78)), Image.LANCZOS))

    def inset(self, x, y, w, h):
        self.d.rounded_rectangle((x, y, x + w, y + h), 5, fill=INSET, outline=EDGE, width=2)

    def label(self, cx, y, s, color=INK, size=20):
        self.text(cx, y, s, size, color, False, "ma")

    # ---- controls (drawn socket + label, and the live widget over it)
    def knob(self, cx, cy, key, label=None, qlink=True):
        self.im.paste(SOCKET, (cx - SOCK // 2, cy - SOCK // 2), SOCKET)
        self.label(cx, cy + SOCK // 2 - 4, label or PARAMS[key]["name"].upper())
        self.widgets.append('knob cx=%d cy=%d r=%d label="" key=%s ns=0 vs=0 bw=%d' % (cx, cy + Y86, SOCK // 2 - 8, key, SOCK))

    def popup(self, cx, cy, key, label, w=150, h=34):
        self.label(cx, cy + h // 2 + 2, label, INK_DIM, 19)
        self.widgets.append('popup cx=%d cy=%d w=%d h=%d label="" key=%s' % (cx, cy + Y86, w, h, key))

    def toggle(self, cx, cy, key, label):
        self.label(cx, cy + 18, label, INK, 19)
        self.widgets.append('toggle cx=%d cy=%d label="" key=%s ns=0' % (cx, cy + Y86, key))

    def when(self, cond):
        self.widgets[-1] += " when=" + cond

    def done(self):
        fn = "images/page_%s.png" % self.name.replace(" ", "_").replace("/", "_")
        self.im.save(os.path.join(OUT, fn))
        emit("")
        emit("[tab %s]" % self.name)
        emit('art x=0 y=%d w=%d h=%d file="%s"' % (Y86, W, H, fn))
        lines.extend(self.widgets)
        emit('qlinks "%s" = %s' % (self.name, ",".join(self.qkeys)))


HEAD = """# Osirus custom skin layout: generated by tools/make_custom.py (edit that, not this file). Every page is drawn there in the Galaxpel look.
theme_bg=222733
theme_panel=3a404f
theme_line=18202c
theme_ink=d1d6e4
theme_ink_dim=8c94a8
theme_accent=75a7fe
theme_accent_hi=a9c8ff
theme_knob_face=2b2f3a
theme_knob_ring=4b5366
theme_knob_dot=75a7fe
theme_lcd=15181f
theme_box=15181f
theme_seg_active=75a7fe
theme_seg_inactive=15181f
theme_seg_active_tx=111216
theme_btn_bg=15181f
theme_btn_text=d1d6e4
theme_btn_text_plain=d1d6e4
theme_display_bg=15181f
theme_display_cell=1d212b
theme_display_off=12151b
theme_display_bezel=0a0b0c
theme_display_ink=79aaff
style=td3
art_css=skin.css
knob_strip=images/knob_galaxpel.png
qlink_bounds=column"""
emit(HEAD)


def row(page, x0, x1, y, items, label_y=None):
    """items spread evenly over x0..x1: ("knob", key, label) / ("popup", key, label, w) / ("toggle", key, label)"""
    n = len(items)
    cw = (x1 - x0) / n
    for i, it in enumerate(items):
        cx = int(x0 + cw * (i + 0.5))
        if it is None:
            continue
        if it[0] == "knob":
            page.knob(cx, y, it[1], it[2] if len(it) > 2 else None)
        elif it[0] == "popup":
            page.popup(cx, y, it[1], it[2], it[3] if len(it) > 3 else int(min(cw - 14, 170)))
        elif it[0] == "toggle":
            page.toggle(cx, y, it[1], it[2])


# ---------------------------------------------------------------- OSC
p = Page("OSC", ["osc1_shape", "osc1_pulsewidth", "osc1_semitone", "osc1_keyfollow", "osc2_shape", "osc2_pulsewidth", "osc2_semitone", "osc2_keyfollow",
                  "osc2_detune", "osc2_fm_amount", "osc2_filt_env_amt", "fm_filt_env_amt", "osc_balance", "osc_mainvolume", "noise_volume", "ringmod_volume"])
p.panel(8, 8, 704, 138, "OSC 1", "osc")
row(p, 20, 700, 84, [("popup", "osc1_wave_select", "WAVE", 150), ("knob", "osc1_shape", "SHAPE"), ("knob", "osc1_pulsewidth", "PULSEWIDTH"),
                     ("knob", "osc1_semitone", "SEMITONE"), ("knob", "osc1_keyfollow", "KEY FOLLOW")])
p.panel(8, 154, 704, 250, "OSC 2", "osc")
row(p, 20, 700, 230, [("popup", "osc2_wave_select", "WAVE", 150), ("knob", "osc2_shape", "SHAPE"), ("knob", "osc2_pulsewidth", "PULSEWIDTH"),
                      ("knob", "osc2_semitone", "SEMITONE"), ("knob", "osc2_keyfollow", "KEY FOLLOW")])
p.inset(16, 282, 688, 114)
row(p, 20, 700, 332, [("popup", "osc_fm_mode", "FM MODE", 150), ("knob", "osc2_fm_amount", "FM AMOUNT"), ("knob", "osc2_detune", "DETUNE"),
                      ("knob", "osc2_filt_env_amt", "ENV OSC2"), ("knob", "fm_filt_env_amt", "ENV FM")])
p.panel(8, 412, 704, 208, "SYNC / SUB / PORTAMENTO", "sub")
row(p, 20, 700, 492, [("toggle", "osc2_sync", "OSC 2 SYNC"), ("toggle", "sub_osc_shape", "SUB WAVE"), ("knob", "sub_osc_volume", "SUB LEVEL"), ("knob", "portamento_time", "PORTAMENTO")])
p.panel(722, 8, 550, 240, "MIXER", "mixer")
row(p, 730, 1264, 78, [("knob", "osc_balance", "OSC BALANCE"), ("knob", "osc_mainvolume", "OSC LEVEL"), ("knob", "noise_color", "NOISE COLOR")])
row(p, 730, 1264, 182, [("knob", "noise_volume", "NOISE"), ("knob", "ringmod_volume", "RING MOD"), None])
p.panel(722, 256, 550, 168, "OSC 3", "osc")
row(p, 730, 1264, 336, [("popup", "osc3_mode", "MODE", 130), ("knob", "osc3_semitone", "SEMITONE"), ("knob", "osc3_detune", "DETUNE"), ("knob", "osc3_volume", "LEVEL")])
p.panel(722, 432, 550, 188, "UNISON", "unison")
row(p, 730, 1264, 524, [("popup", "unison_mode", "VOICES", 100), ("knob", "unison_detune", "DETUNE"), ("knob", "unison_pan_spread", "PAN SPREAD"),
                        ("knob", "unison_lfo_phase", "LFO PHASE"), ("knob", "osc_init_phase", "PHASE INIT")])
p.done()

# ---------------------------------------------------------------- FILTER
p = Page("FILTER", ["cutoff", "filter1_resonance", "filter1_env_amt", "filter1_keyfollow", "resonance1_velocity", "flt1_envamt_velocity", "-", "-",
                    "cutoff2_offset", "filter2_resonance", "filter2_env_amt", "filter2_keyfollow", "resonance2_velocity", "flt2_envamt_velocity", "-", "-"])
p.panel(8, 8, 1264, 612, "FILTERS", "filters")
row(p, 20, 1260, 100, [("knob", "cutoff", "CUTOFF 1"), ("knob", "filter1_resonance", "RESONANCE 1"), ("knob", "filter1_env_amt", "ENV 1 AMT"),
                       ("knob", "filter1_keyfollow", "KEYTRACK 1"), ("knob", "resonance1_velocity", "RES 1 VEL"), ("knob", "flt1_envamt_velocity", "ENV 1 VEL")])
p.inset(60, 196, 1160, 232)
row(p, 70, 460, 262, [("popup", "filter1_mode", "FILTER 1 MODE", 180)])
row(p, 70, 460, 366, [("popup", "filter2_mode", "FILTER 2 MODE", 180)])
row(p, 460, 820, 312, [("knob", "filter_balance", "FILTER BALANCE")])
row(p, 800, 1210, 262, [("popup", "filter_routing", "ROUTING", 180), ("knob", "filter_keytrack_base", "KEY BASE")])
row(p, 800, 1210, 366, [("popup", "saturation_curve", "SATURATION", 180), ("toggle", "filter1_env_polarity", "ENV 1 POL")])
row(p, 20, 1260, 524, [("knob", "cutoff2_offset", "CUTOFF 2"), ("knob", "filter2_resonance", "RESONANCE 2"), ("knob", "filter2_env_amt", "ENV 2 AMT"),
                       ("knob", "filter2_keyfollow", "KEYTRACK 2"), ("knob", "resonance2_velocity", "RES 2 VEL"), ("knob", "flt2_envamt_velocity", "ENV 2 VEL")])
p.done()

# ---------------------------------------------------------------- ENV
p = Page("ENV", ["flt_attack", "flt_decay", "flt_sustain", "flt_release", "amp_attack", "amp_decay", "amp_sustain", "amp_release", "flt_sustain_time", "amp_sustain_time"])
p.panel(8, 8, 1264, 300, "FLT ENV", "env")
row(p, 20, 1260, 130, [("knob", "flt_attack", "ATTACK"), ("knob", "flt_decay", "DECAY"), ("knob", "flt_sustain", "SUSTAIN"), ("knob", "flt_sustain_time", "TIME"), ("knob", "flt_release", "RELEASE")])
p.panel(8, 320, 1264, 300, "AMP ENV", "env")
row(p, 20, 1260, 442, [("knob", "amp_attack", "ATTACK"), ("knob", "amp_decay", "DECAY"), ("knob", "amp_sustain", "SUSTAIN"), ("knob", "amp_sustain_time", "TIME"), ("knob", "amp_release", "RELEASE")])
p.done()

open(os.path.join(OUT, "layout.conf"), "w").write("\n".join(lines) + "\n")
v = json.load(open(os.path.join(ROOT, "vst", "vst.json")))
v.update(name="Osirus Custom", layout="layout.conf", build={"root": "../..", "sources": [], "cflags": [], "libs": ["-lm"]})
for k in ("tile", "skin_post"):
    v.pop(k, None)
json.dump(v, open(os.path.join(OUT, "vst.json"), "w"), indent=2)
print(OUT)
