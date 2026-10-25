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
INSTALL = "--install" in __import__("sys").argv       # write the plugin's real layout (vst/layout.conf, vst/images/page_*.png)
OUT = os.path.join(ROOT, "vst") if INSTALL else os.path.join(ROOT, "vst", "custom")
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
SOCK = 72                   # knob socket size on screen: 104 px art scaled down

os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
if not INSTALL:
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
        self.label(cx, cy + SOCK // 2 - 2, label or PARAMS[key]["name"].upper(), INK, 18)
        # the live value goes under the baked label (vy=): vs=15 px text, 22 px below the knob's own value row
        self.widgets.append('knob cx=%d cy=%d r=%d label="" key=%s ns=0 vs=15 vy=22 bw=%d' % (cx, cy + Y86, SOCK // 2 - 6, key, SOCK + 24))

    def popup(self, cx, cy, key, label, w=150, h=34):
        self.label(cx, cy + h // 2 + 2, label, INK_DIM, 19)
        self.widgets.append('popup cx=%d cy=%d w=%d h=%d label="" key=%s' % (cx, cy + Y86, w, h, key))

    def toggle(self, cx, cy, key, label):
        self.label(cx, cy + 18, label, INK, 19)
        self.widgets.append('toggle cx=%d cy=%d label="" key=%s ns=0' % (cx, cy + Y86, key))

    def readout(self, cx, cy, key, label, w=300, h=34):
        self.label(cx, cy - h // 2 - 22, label, INK_DIM, 19)
        self.widgets.append('readout cx=%d cy=%d w=%d h=%d label="" key=%s' % (cx, cy + Y86, w, h, key))

    def button(self, cx, cy, key, label, w=130, h=40):
        self.widgets.append('button cx=%d cy=%d label="%s" key=%s' % (cx, cy + Y86, label, key))

    def layer(self, rect, cond):
        """Context manager: what is drawn inside is a separate image shown only while <cond> (when=<param>:<option>)."""
        page = self

        class _L:
            def __enter__(s_):
                s_.saved = (page.im, page.d, page.widgets)
                page.im = page.im.copy()
                page.d = ImageDraw.Draw(page.im)
                page.widgets = []
                return page

            def __exit__(s_, *a):
                im, wid = page.im, page.widgets
                page.im, page.d, page.widgets = s_.saved
                x0, y0, x1, y1 = rect
                page.n_layers = getattr(page, "n_layers", 0) + 1
                fn = "images/page_%s_L%d.png" % (page.name.replace(" ", "_").replace("/", "_"), page.n_layers)
                im.crop(rect).save(os.path.join(OUT, fn))
                page.widgets.append('art x=%d y=%d w=%d h=%d file="%s" when=%s' % (x0, y0 + Y86, x1 - x0, y1 - y0, fn, cond))
                page.widgets.extend(w + " when=" + cond for w in wid)
        return _L()

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
        elif it[0] == "readout":
            page.readout(cx, y, it[1], it[2], it[3] if len(it) > 3 else int(cw - 20))
        elif it[0] == "button":
            page.button(cx, y, it[1], it[2])


# ---------------------------------------------------------------- PLAY
def header(page):
    """our own title bar: Galaxpel's OSIRUS wordmark (skin/parts/wordmark.png, cut from its main background) and a display bezel with its blue glow,
    holding the bank and preset steppers"""
    d = page.d
    page.panel(8, 6, 1264, 118, "")
    wm = Image.open(os.path.join(PARTS, "wordmark.png")).convert("RGBA")
    wm = wm.resize((int(wm.width * 0.72), int(wm.height * 0.72)), Image.LANCZOS)
    page.im.paste(wm, (34, 12), wm)
    d.rounded_rectangle((372, 16, 1256, 114), 8, fill=(22, 25, 33), outline=(15, 17, 23), width=3)       # the bezel
    d.rounded_rectangle((376, 20, 1252, 110), 6, outline=(70, 78, 98), width=1)
    for i in range(160):                                                                                   # Galaxpel's blue glow along the top edge
        a = int(150 * (1 - abs(i - 80) / 80))
        d.line((572 + i * 3, 19, 572 + i * 3 + 3, 19), fill=(60 + a // 4, 100 + a // 2, 200 + a // 4))
    page.text(404, 20, "BANK", 20, INK_DIM)
    page.text(764, 20, "PRESET", 20, INK_DIM)
    # the preset stepper comes first: the data wheel acts on the first focusable control
    page.widgets.append('stepper w=500 h=44 cx=%d cy=%d label="" key=preset get=preset_name prev=preset_prev next=preset_next style=dotmatrix persistent=1' % (1000, 78 + Y86))
    page.widgets.append('stepper w=300 h=44 cx=%d cy=%d label="" key=bank_index get=bank_name prev=bank_prev next=bank_next style=dotmatrix persistent=1' % (550, 78 + Y86))


p = Page("PLAY", ["preset", "bank_index", "-", "-", "patch_volume", "panorama", "transpose", "-", "gain", "dsp_clock", "octave_transpose", "rom_index",
                  "bender_range_up", "bender_range_down", "-", "-"])
header(p)
p.panel(8, 132, 520, 214, "PATCH SETTINGS", "patch")
row(p, 16, 520, 214, [("popup", "key_mode", "KEY MODE", 130), ("knob", "patch_volume", "PATCH VOLUME"), ("knob", "panorama", "PANNING"), ("knob", "transpose", "TRANSPOSE")])
p.panel(536, 132, 736, 214, "ENGINE", None)
p.readout(904, 205, "rom_name", "ROM", 704)
p.readout(722, 262, "loading_status", "STATUS", 340)
p.readout(1088, 262, "engine_stats", "STATS", 340)
p.button(722, 318, "all_notes_off", "PANIC")
p.button(1088, 318, "init_patch", "INIT PATCH")
p.panel(8, 354, 1264, 266, "OUTPUT", None)
row(p, 16, 1264, 470, [("knob", "gain", "GAIN %"), ("knob", "dsp_clock", "DSP CLOCK %"), ("knob", "octave_transpose", "OCTAVE"), ("knob", "rom_index", "ROM NUMBER"),
                       ("knob", "bender_range_up", "BEND UP"), ("knob", "bender_range_down", "BEND DOWN")])
p.done()

# ---------------------------------------------------------------- BANKS
p = Page("BANKS", ["preset", "bank_index", "patch_page_prev", "patch_page_next"])
p.widgets.append('stepper w=560 h=44 cx=520 cy=%d label="" key=preset get=preset_name prev=preset_prev next=preset_next style=dotmatrix persistent=1' % (30 + Y86))
p.widgets.append('stepper w=250 h=44 cx=150 cy=%d label="" key=bank_index get=bank_name prev=bank_prev next=bank_next style=dotmatrix persistent=1' % (30 + Y86))
p.widgets.append('stepper w=240 h=44 cx=1120 cy=%d label="" key=patch_page_text get=patch_page_text prev=patch_page_prev next=patch_page_next style=dotmatrix' % (30 + Y86))
p.panel(8, 62, 262, 558, "BANKS", "patch")
p.widgets.append('list x=22 y=%d w=236 h=486 cols=1 rows=16 gap=4 th=27 key=bank_slot' % (112 + Y86))
p.panel(278, 62, 994, 558, "PATCHES", "patch")
p.widgets.append('list x=292 y=%d w=966 h=486 cols=3 rows=10 gap=6 th=41 key=patch_slot order=cols' % (112 + Y86))
p.done()

# ---------------------------------------------------------------- OSC
p = Page("OSC", ["osc1_shape", "osc1_pulsewidth", "osc1_semitone", "osc1_keyfollow", "osc2_shape", "osc2_pulsewidth", "osc2_semitone", "osc2_keyfollow",
                  "osc2_detune", "osc2_fm_amount", "osc2_filt_env_amt", "fm_filt_env_amt", "osc3_semitone", "osc3_detune", "osc3_volume", "-"])
p.panel(8, 8, 704, 158, "OSC 1", "osc")
row(p, 20, 700, 82, [("popup", "osc1_wave_select", "WAVE", 150), ("knob", "osc1_shape", "SHAPE"), ("knob", "osc1_pulsewidth", "PULSEWIDTH"),
                     ("knob", "osc1_semitone", "SEMITONE"), ("knob", "osc1_keyfollow", "KEY FOLLOW")])
p.panel(8, 174, 704, 282, "OSC 2", "osc")
row(p, 20, 700, 248, [("popup", "osc2_wave_select", "WAVE", 150), ("knob", "osc2_shape", "SHAPE"), ("knob", "osc2_pulsewidth", "PULSEWIDTH"),
                      ("knob", "osc2_semitone", "SEMITONE"), ("knob", "osc2_keyfollow", "KEY FOLLOW")])
p.inset(16, 330, 688, 118)
row(p, 20, 700, 368, [("popup", "osc_fm_mode", "FM MODE", 150), ("knob", "osc2_fm_amount", "FM AMOUNT"), ("knob", "osc2_detune", "DETUNE"),
                      ("knob", "osc2_filt_env_amt", "ENV OSC2"), ("knob", "fm_filt_env_amt", "ENV FM")])
p.panel(8, 464, 704, 156, "OSC 3", "osc")
row(p, 20, 700, 538, [("popup", "osc3_mode", "OSC 3 MODE", 150), ("knob", "osc3_semitone", "SEMITONE"), ("knob", "osc3_detune", "DETUNE"), ("knob", "osc3_volume", "LEVEL")])
p.panel(722, 8, 550, 282, "MIXER", "mixer")
row(p, 730, 1264, 82, [("knob", "osc_balance", "OSC BALANCE"), ("knob", "osc_mainvolume", "OSC LEVEL"), ("knob", "noise_color", "NOISE COLOR")])
row(p, 730, 1264, 198, [("knob", "noise_volume", "NOISE"), ("knob", "ringmod_volume", "RING MOD"), None])
p.panel(722, 298, 550, 158, "SYNC / SUB / PORTAMENTO", "sub")
row(p, 730, 1264, 372, [("toggle", "osc2_sync", "OSC 2 SYNC"), ("toggle", "sub_osc_shape", "SUB WAVE"), ("knob", "sub_osc_volume", "SUB LEVEL"), ("knob", "portamento_time", "PORTAMENTO")])
p.panel(722, 464, 550, 156, "UNISON", "unison")
row(p, 730, 1264, 538, [("popup", "unison_mode", "VOICES", 100), ("knob", "unison_detune", "DETUNE"), ("knob", "unison_pan_spread", "PAN SPREAD"),
                        ("knob", "unison_lfo_phase", "LFO PHASE"), ("knob", "osc_init_phase", "PHASE INIT")])
p.done()

# ---------------------------------------------------------------- FILTER
p = Page("FILTER", ["cutoff", "filter1_resonance", "filter1_env_amt", "filter1_keyfollow", "resonance1_velocity", "flt1_envamt_velocity", "-", "-",
                    "cutoff2_offset", "filter2_resonance", "filter2_env_amt", "filter2_keyfollow", "resonance2_velocity", "flt2_envamt_velocity", "-", "-"])
p.panel(8, 8, 1264, 612, "FILTERS", "filters")
row(p, 20, 1260, 84, [("knob", "cutoff", "CUTOFF 1"), ("knob", "filter1_resonance", "RESONANCE 1"), ("knob", "filter1_env_amt", "ENV 1 AMT"),
                      ("knob", "filter1_keyfollow", "KEYTRACK 1"), ("knob", "resonance1_velocity", "RES 1 VEL"), ("knob", "flt1_envamt_velocity", "ENV 1 VEL")])
p.inset(60, 180, 1160, 250)
row(p, 70, 460, 244, [("popup", "filter1_mode", "FILTER 1 MODE", 180)])
row(p, 70, 460, 366, [("popup", "filter2_mode", "FILTER 2 MODE", 180)])
row(p, 460, 820, 304, [("knob", "filter_balance", "FILTER BALANCE")])
row(p, 800, 1210, 244, [("popup", "filter_routing", "ROUTING", 180), ("knob", "filter_keytrack_base", "KEY BASE")])
row(p, 800, 1210, 366, [("popup", "saturation_curve", "SATURATION", 180), ("toggle", "filter1_env_polarity", "ENV 1 POL")])
row(p, 20, 1260, 520, [("knob", "cutoff2_offset", "CUTOFF 2"), ("knob", "filter2_resonance", "RESONANCE 2"), ("knob", "filter2_env_amt", "ENV 2 AMT"),
                       ("knob", "filter2_keyfollow", "KEYTRACK 2"), ("knob", "resonance2_velocity", "RES 2 VEL"), ("knob", "flt2_envamt_velocity", "ENV 2 VEL")])
p.done()

# ---------------------------------------------------------------- ENV
p = Page("ENV", ["flt_attack", "flt_decay", "flt_sustain", "flt_release", "amp_attack", "amp_decay", "amp_sustain", "amp_release", "flt_sustain_time", "amp_sustain_time"])
p.panel(8, 8, 1264, 300, "FLT ENV", "env")
row(p, 20, 1260, 130, [("knob", "flt_attack", "ATTACK"), ("knob", "flt_decay", "DECAY"), ("knob", "flt_sustain", "SUSTAIN"), ("knob", "flt_sustain_time", "TIME"), ("knob", "flt_release", "RELEASE")])
p.panel(8, 320, 1264, 300, "AMP ENV", "env")
row(p, 20, 1260, 442, [("knob", "amp_attack", "ATTACK"), ("knob", "amp_decay", "DECAY"), ("knob", "amp_sustain", "SUSTAIN"), ("knob", "amp_sustain_time", "TIME"), ("knob", "amp_release", "RELEASE")])
p.done()

# ---------------------------------------------------------------- LFO 1 + 2
p = Page("LFO 1+2", ["lfo1_rate", "lfo1_keyfollow", "lfo1_symmetry", "lfo1_keytrigger", "osc1_lfo1_amount", "osc2_lfo1_amount", "pw_lfo1_amount", "reso_lfo1_amount",
                     "lfo2_rate", "lfo2_keyfollow", "lfo2_symmetry", "lfo2_keytrigger", "cutoff1_lfo2_amount", "cutoff2_lfo2_amount", "shape_lfo2_amount", "fm_lfo2_amount"])
p.panel(8, 8, 1264, 304, "LFO 1", "osc")
row(p, 16, 1264, 84, [("popup", "lfo1_shape", "SHAPE", 140), ("knob", "lfo1_rate", "RATE"), ("knob", "lfo1_keyfollow", "KEYTRACK"), ("knob", "lfo1_symmetry", "CONTOUR"),
                      ("knob", "lfo1_keytrigger", "PHASE"), ("knob", "osc1_lfo1_amount", "OSC 1 PITCH"), ("knob", "osc2_lfo1_amount", "OSC 2 PITCH"), ("knob", "pw_lfo1_amount", "PW 1+2")])
row(p, 16, 1264, 204, [("popup", "lfo1_clock", "CLOCK", 140), ("toggle", "lfo1_mode", "POLY / MONO"), ("toggle", "lfo1_env_mode", "ENV MODE"), ("knob", "reso_lfo1_amount", "RESO 1+2"),
                       ("knob", "filtgain_lfo1_amount", "FILTER GAIN"), ("knob", "lfo1_assign_amount", "ASSIGN AMOUNT"), ("popup", "lfo1_assign_dest", "ASSIGN DESTINATION", 140), None])
p.panel(8, 320, 1264, 300, "LFO 2", "osc")
row(p, 16, 1264, 396, [("popup", "lfo2_shape", "SHAPE", 140), ("knob", "lfo2_rate", "RATE"), ("knob", "lfo2_keyfollow", "KEYTRACK"), ("knob", "lfo2_symmetry", "CONTOUR"),
                       ("knob", "lfo2_keytrigger", "PHASE"), ("knob", "cutoff1_lfo2_amount", "F1 CUTOFF"), ("knob", "cutoff2_lfo2_amount", "F2 CUTOFF"), ("knob", "shape_lfo2_amount", "SHAPE 1+2")])
row(p, 16, 1264, 514, [("popup", "lfo2_clock", "CLOCK", 140), ("toggle", "lfo2_mode", "POLY / MONO"), ("toggle", "lfo2_env_mode", "ENV MODE"), ("knob", "fm_lfo2_amount", "FM AMOUNT"),
                       ("knob", "pan_lfo2_amount", "PANNING"), ("knob", "lfo2_assign_amount", "ASSIGN AMOUNT"), ("popup", "lfo2_assign_dest", "ASSIGN DESTINATION", 140), None])
p.done()

# ---------------------------------------------------------------- LFO 3 / ARP
p = Page("LFO 3 / ARP", ["lfo3_rate", "lfo3_keyfollow", "lfo3_fadein_time", "osc_lfo3_amount", "arp_pattern", "arp_note_length", "arp_swing", "clock_tempo"])
p.panel(8, 8, 1264, 290, "LFO 3", "osc")
row(p, 16, 1264, 84, [("popup", "lfo3_shape", "SHAPE", 140), ("knob", "lfo3_rate", "RATE"), ("knob", "lfo3_keyfollow", "KEYTRACK"), ("knob", "lfo3_fadein_time", "FADE IN"),
                      ("knob", "osc_lfo3_amount", "AMOUNT"), ("popup", "lfo3_destination", "DESTINATION", 140)])
row(p, 16, 1264, 204, [("popup", "lfo3_clock", "CLOCK", 140), ("toggle", "lfo3_mode", "POLY / MONO")])
p.panel(8, 306, 1264, 314, "ARPEGGIATOR", "arp")
row(p, 16, 1264, 380, [("popup", "arp_mode", "MODE", 140), ("popup", "arp_octave_range", "OCTAVES", 140), ("popup", "arp_clock", "RESOLUTION", 140), ("toggle", "arp_hold", "ARP HOLD")])
row(p, 16, 1264, 510, [("knob", "arp_pattern", "PATTERN"), ("knob", "arp_note_length", "NOTE LENGTH"), ("knob", "arp_swing", "NOTE SWING"), ("knob", "clock_tempo", "GLOBAL TEMPO")])
p.done()

# ---------------------------------------------------------------- MOD
p = Page("MOD", ["assign1_amount", "-", "-", "-", "assign2_amount1", "assign2_amount2", "-", "-", "assign3_amount1", "assign3_amount2", "assign3_amount3", "-"])


def slot(page, x, w, n, dests, top=8):
    """a modulation slot: its source popup, then one row per destination (amount knob and destination popup)"""
    page.panel(x, top, w, 44 + 62 + 112 * len(dests) + 12, "SLOT %d" % n, "mixer")
    page.popup(x + w // 2, top + 74, "assign%d_source" % n, "SOURCE", w - 40, 34)
    for i, (dk, ak) in enumerate(dests):
        cy = top + 150 + 112 * i
        page.knob(x + 66, cy, ak, "AMOUNT")
        page.popup(x + 66 + (w - 66) // 2 + 20, cy - 8, dk, "DESTINATION", w - 150, 34)


slot(p, 8, 414, 1, [("assign1_destination", "assign1_amount")])
slot(p, 432, 414, 2, [("assign2_dest1", "assign2_amount1"), ("assign2_dest2", "assign2_amount2")])
slot(p, 856, 416, 3, [("assign3_dest1", "assign3_amount1"), ("assign3_dest2", "assign3_amount2"), ("assign3_dest3", "assign3_amount3")])
# slots 4-6 exist on a Virus B or C only: a separate layer shown while rom_bc is Yes
with p.layer((0, 468, 1280, 628), "rom_bc:Yes"):
    p.panel(8, 468, 1264, 152, "SLOTS 4 - 6 (VIRUS B / C)", "mixer")
    for i, n in enumerate((4, 5, 6)):
        x0 = 16 + i * 420
        p.popup(x0 + 90, 548, "assign%d_source" % n, "SOURCE %d" % n, 150, 34)
        p.popup(x0 + 250, 548, "assign%d_destination" % n, "DESTINATION", 150, 34)
        p.knob(x0 + 370, 548, "assign%d_amount" % n, "AMOUNT")
p.done()

# ---------------------------------------------------------------- FX 1
p = Page("FX 1", ["distortion_intensity", "bass_intensity", "bass_tune", "punch_intensity", "phaser_rate", "phaser_frequency", "phaser_depth", "phaser_feedback",
                  "chorus_rate", "chorus_depth", "chorus_feedback", "chorus_delay", "phaser_spread", "phaser_mix", "chorus_mix", "-"])
p.panel(8, 8, 440, 158, "DISTORTION", "dist")
row(p, 16, 448, 82, [("popup", "distortion_curve", "CURVE", 130), ("knob", "distortion_intensity", "INTENSITY")])
p.panel(456, 8, 420, 158, "ANALOG BOOST", "analog")
row(p, 464, 876, 82, [("knob", "bass_intensity", "BOOST"), ("knob", "bass_tune", "TUNE")])
p.panel(884, 8, 388, 158, "PUNCH", "punch")
row(p, 892, 1264, 82, [("knob", "punch_intensity", "AMOUNT")])
p.panel(8, 174, 1264, 158, "PHASER", "phaser")
row(p, 16, 1264, 248, [("popup", "phaser_mode", "STAGES", 130), ("knob", "phaser_rate", "RATE"), ("knob", "phaser_frequency", "FREQUENCY"), ("knob", "phaser_depth", "DEPTH"),
                       ("knob", "phaser_feedback", "FEEDBACK"), ("knob", "phaser_spread", "SPREAD"), ("knob", "phaser_mix", "MIX")])
p.panel(8, 340, 1264, 158, "CHORUS", "chorus")
row(p, 16, 1264, 414, [("popup", "chorus_lfo_shape", "LFO SHAPE", 130), ("knob", "chorus_rate", "RATE"), ("knob", "chorus_depth", "DEPTH"), ("knob", "chorus_feedback", "FEEDBACK"),
                       ("knob", "chorus_delay", "DELAY"), ("knob", "chorus_mix", "MIX")])
p.done()

# ---------------------------------------------------------------- FX 2
p = Page("FX 2", ["low_eq_gain", "low_eq_freq", "mid_eq_gain", "mid_eq_freq", "mid_eq_q", "high_eq_gain", "high_eq_freq", "-",
                  "delay_time", "delay_feedback", "delay_color", "delay_rate_rev_decay", "delay_depth", "effect_send", "-", "-"])
p.panel(8, 8, 1264, 158, "EQUALIZER", "eq")
row(p, 16, 1264, 82, [("knob", "low_eq_gain", "LOW GAIN"), ("knob", "low_eq_freq", "LOW FREQ"), ("knob", "mid_eq_gain", "MID GAIN"), ("knob", "mid_eq_freq", "MID FREQ"),
                      ("knob", "mid_eq_q", "MID Q"), ("knob", "high_eq_gain", "HIGH GAIN"), ("knob", "high_eq_freq", "HIGH FREQ")])
p.panel(8, 174, 1264, 282, "DELAY / REVERB", "delay")
row(p, 16, 1264, 248, [("popup", "delay_reverb_mode", "FX MODE", 140), ("knob", "effect_send", "SEND"), ("knob", "delay_time", "TIME"), ("knob", "delay_feedback", "FEEDBACK"),
                       ("knob", "delay_color", "COLOR"), ("knob", "delay_rate_rev_decay", "RATE / DECAY"), ("knob", "delay_depth", "DEPTH")])
row(p, 16, 1264, 364, [("popup", "delay_clock", "CLOCK", 140), ("popup", "delay_lfo_shape", "LFO SHAPE", 140)])
p.done()

# ---------------------------------------------------------------- VELOCITY
p = Page("VELOCITY", ["osc1_shape_velocity", "flt1_envamt_velocity", "resonance1_velocity", "pulsewidth_velocity", "amp_velocity", "panorama_velocity", "-", "-",
                      "osc2_shape_velocity", "flt2_envamt_velocity", "resonance2_velocity", "fm_amount_velocity"])
p.panel(8, 8, 1264, 612, "VELOCITY AMOUNTS", "velo")
row(p, 16, 1264, 170, [("knob", "osc1_shape_velocity", "OSC 1 SHAPE"), ("knob", "flt1_envamt_velocity", "FLT 1 ENV"), ("knob", "resonance1_velocity", "FLT 1 RES"),
                       ("knob", "pulsewidth_velocity", "PULSEWIDTH"), ("knob", "amp_velocity", "VOLUME"), ("knob", "panorama_velocity", "PANORAMA")])
row(p, 16, 1264, 400, [("knob", "osc2_shape_velocity", "OSC 2 SHAPE"), ("knob", "flt2_envamt_velocity", "FLT 2 ENV"), ("knob", "resonance2_velocity", "FLT 2 RES"),
                       ("knob", "fm_amount_velocity", "FM AMOUNT")])
p.done()

open(os.path.join(OUT, "layout.conf"), "w").write("\n".join(lines) + "\n")
if not INSTALL:
    v = json.load(open(os.path.join(ROOT, "vst", "vst.json")))
    v.update(name="Osirus Custom", layout="layout.conf", build={"root": "../..", "sources": [], "cflags": [], "libs": ["-lm"]})
    for k in ("tile", "skin_post"):
        v.pop(k, None)
    json.dump(v, open(os.path.join(OUT, "vst.json"), "w"), indent=2)
print(OUT)
