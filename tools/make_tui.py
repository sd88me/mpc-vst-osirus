#!/usr/bin/env python3
"""Osirus's native MPC skin: skins/TUI.json + skins/Q-Links.json + the PNGs they use (docs/SDK-PORTING.md, after Xenia's tools/make_tui.py).

The pages are the 0.2.11 pages: the Galaxpel art of tools/make_custom.py (vst/images/page_*.png: sections, sockets, captions) with native
widgets at the positions of vst/layout.conf and the released skin's geometry (a 96 x 125 knob block: the 70 px Galaxpel knob, its value
30 px under it; popup fields w x 34; the switch pill 53 x 37). Popups become drawn pick-lists on ONE ui_open parameter (index 257; value
k + 1 = the k-th popup of params.lock, the front end's order). Widgets marked when=rom_bc:Yes show only with a Virus B or C ROM
(IndexedEnabling on rom_bc, index 250). Q-Links: the layout's 16-key sets as blocks of four, each framed round its controls.
    python3 tools/make_tui.py              # -> skins/   (build-sdk.sh copies it to Plugin Skins/)
    python3 tools/make_tui.py --preview    # also docs/skin-preview/<tab>.png, composed offline (Titillium at the MPC's text scale)"""
import hashlib, json, os, re, shutil, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OSIRUS_SKIN_OUT", os.path.join(ROOT, "skins"))
PREVIEW = os.path.join(ROOT, "docs", "skin-preview")
VST_IMG = os.path.join(ROOT, "vst", "images")
FONT = os.path.join(ROOT, "vst", "fonts", "BebasNeue-Regular.ttf")    # the Galaxpel captions (OFL)
TIT = os.path.join(ROOT, "tools", "fonts", "TitilliumWeb-SemiBold.ttf")   # the preview only: the MPC draws live text in Titillium Web
LOCK = [l.strip() for l in open(os.path.join(ROOT, "params.lock")) if l.strip()]
PARAMS = {p["key"]: p for p in json.load(open(os.path.join(ROOT, "vst", "params.json")))["params"]}
POPUPS = [k[:-len("__open")] for k in LOCK if k.endswith("__open")]
UI_INDEX = LOCK.index(POPUPS[0] + "__open")          # 257: ui_open sits in the first popup slot
UI_STEPS = len(POPUPS) + 1                           # 0 closed, k + 1 = pick-list k
ROM_BC = LOCK.index("rom_bc")                        # 250 (the duplicate at 251 is an inert slot)
TUI_PX = 0.66                                        # a Label draws its text at about 0.66 x its height (Crate Digger, on the device)
GESTURE = "Instant"

# ---- the Galaxpel palette (vst/layout.conf theme_*) ------------------------------------------------------------------------
PANEL = (58, 64, 79)
BOX = (21, 24, 31)
BEZEL = (10, 11, 12)
INK = (209, 214, 228)
DIM = (140, 148, 168)
ACCENT = (117, 167, 254)
ACCENT_HI = (169, 200, 255)
DISPLAY_INK = (121, 170, 255)
DARK_TEXT = (17, 18, 22)


def hexc(c, a=255):
    return "%02x%02x%02x%02x" % ((a,) + tuple(c))


def PI(key):
    return UI_INDEX if key == "ui_open" else LOCK.index(key)


def P(key):
    return "Parameter %d" % PI(key)


# ---- a JSON writer that keeps key order and allows the overlay widgets' duplicate "version" key ------------------------------
class Obj:
    def __init__(self, *pairs):
        self.pairs = list(pairs)


def dump(v, ind=0):
    sp = "  " * ind
    pairs = v.pairs if hasattr(v, "pairs") else list(v.items()) if isinstance(v, dict) else None
    if pairs is not None:
        if not pairs:
            return "{}"
        return "{\n%s\n%s}" % (",\n".join("%s  %s: %s" % (sp, dump(k), dump(x, ind + 1)) for k, x in pairs), sp)
    if isinstance(v, list):
        return "[]" if not v else "[\n%s\n%s]" % (",\n".join(sp + "  " + dump(x, ind + 1) for x in v), sp)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v) if isinstance(v, float) else str(v)
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')


# ---- TUI building blocks --------------------------------------------------------------------------------------------------
def bounds(b, focus="No", ind=None):
    d = {"version": 2 if ind else 1, "acceptsHWFocus": focus, "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
         "boundsType": "Absolute", "bounds": b}
    if ind:
        d["additionalInvalidatingHandles"] = ind
    return d


def entry(name, typ, data, b, remap=None, focus="No", ind=None, visible=None):
    e = {"version": 2, "componentData": {"version": 1, "name": name, "type": typ, "data": data},
         "handle remapping": {"version": 1, "map": [{"key": "Data", "value": remap}] if remap else []},
         "bounds": bounds(b, focus, ind)}
    if visible:
        e["bounds"]["whenVisible"] = visible
    return e


def bg(colour="0", image=""):
    return {"version": 1, "focussed": {"version": 1, "colour": colour, "image": image}, "unfocussed": {"version": 1, "colour": colour, "image": image}}


def component(children, actions=None, ignore=False, background=None):
    return {"version": 2, "actions": actions or [], "backgroundData": background or bg(), "ignoreMousePresses": ignore,
            "disableCoarseDataWheel": False, "componentsData": children}


def act(on, handler, extra=""):
    return {"version": 1, "onAction": on, "handler": handler, "handleName": "Data", "additionalData": extra}


def text_style(h, colour, just="horizontallyCentred verticallyCentred", style="SemiBold"):
    return {"version": 1, "font": {"version": 1, "name": "Titillium Web", "style": style, "height": float(h)}, "colour": colour,
            "justification": just, "case": "Original"}


def label(b, key, h=20, colour=None, just="horizontallyCentred verticallyCentred", style="SemiBold", ind=None):
    return entry("label", "Label", {"version": 1, "textStyle": text_style(h, colour or hexc(INK), just, style), "type": "Value",
                                    "handleName": "Data"}, b, P(key), ind=ind)


KNOB, KW, KH = 70, 96, 125    # the 0.2.11 knob block: the knob at (13, 0), the value label at (0, 89, 96, 30)
FOCUS = {"version": 1, "backgroundColour": "00000000", "outlineColour": hexc(ACCENT), "backgroundInset": 4.0, "outlineThickness": 2.0}
FIELDS = set()                                         # (w, h) of every stepper name field (an invisible value slider over it)
FIELD_KEY = {"bank_name": "bank_index", "preset_name": "preset"}


def definitions():
    knob = component([
        entry("focus", "Focus", FOCUS, "7 -6 %d %d" % (KNOB + 12, KNOB + 12), visible="WhenFocussed"),
        entry("knob", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": "knob_galaxpel70.png", "numFrames": KNOB_FRAMES,
                               "invert": False, "dragOrientation": "Vertical", "handleName": "Data"}, "13 0 %d %d" % (KNOB, KNOB)),
        entry("value", "Label", {"version": 1, "textStyle": text_style(22, hexc(DIM)), "type": "Value", "handleName": "Data"}, "0 89 96 30"),
    ], actions=[act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "knob overlay"), act("Enter Pressed", "Show Overlay", "knob overlay")])
    knob_overlay = component([entry("overlay", "KnobOverlay", Obj(
        ("version", 2), ("version", 1),
        ("actions", [{"version": 1, "onAction": "Focus Lost", "handler": "Focus Lost", "handleName": "Focus Lost", "additionalData": ""}]),
        ("overlayType", "Knob With Header"), ("scaleType", "Linear"), ("polarityType", "Unipolar"),
        ("showMinusSign", True), ("handleName", "Data")), "0 0 1280 800", focus="Yes")], ignore=True)
    toggle = component([
        entry("focus", "Focus", FOCUS, "0 0 53 37", visible="WhenFocussed"),
        entry("pill", "Button", {"version": 2, "onImage": "pill_on.png", "offImage": "pill_off.png", "buttonId": 1, "numButtonsInGroup": 1,
                                 "handleName": "Data", "gestureBehaviour": GESTURE}, "0 4 53 29"),
    ], actions=[act("Mouse Down", "Q-Link"), act("Enter Pressed", "Toggle Switch")])
    out = [{"key": "gknob", "value": knob}, {"key": "knob overlay", "value": knob_overlay}, {"key": "gtoggle", "value": toggle}]
    for w, h in sorted(FIELDS):   # a stepper's name: the data wheel, a Q-Link or a drag steps its value
        ts = {"version": 1, "font": {"version": 1, "name": "Roboto", "style": "Regular", "height": 20.0}, "colour": "00000000",
              "justification": "horizontallyCentred verticallyCentred", "case": "Original"}
        out.append({"key": "field%dx%d" % (w, h), "value": component([
            entry("focus", "Focus", FOCUS, "0 0 %d %d" % (w, h), visible="WhenFocussed"),
            entry("field", "Knob", {"version": 4, "knobType": "ValueSlider", "textStyle": ts, "dragOrientation": "Horizontal",
                                    "handleName": "Data"}, "0 0 %d %d" % (w, h)),
        ], actions=[act("Mouse Down", "Q-Link")])})
    return out


# ---- art ---------------------------------------------------------------------------------------------------------------------
_fonts = {}


def F(size, path=None):
    path = path or FONT
    if (size, path) not in _fonts:
        _fonts[(size, path)] = ImageFont.truetype(path, size)
    return _fonts[(size, path)]


def save(im, name):
    im.save(os.path.join(OUT, name))
    return name


KNOB_FRAMES = 101


def knob_strip():
    """The Galaxpel knob film strip of 0.2.11 (vst/images/knob_galaxpel.png, 104 px frames), at 70 px."""
    src = Image.open(os.path.join(VST_IMG, "knob_galaxpel.png")).convert("RGBA")
    n = src.height // src.width
    assert n == KNOB_FRAMES, n
    out = Image.new("RGBA", (KNOB, KNOB * n), (0, 0, 0, 0))
    for i in range(n):
        out.paste(src.crop((0, i * src.width, src.width, (i + 1) * src.width)).resize((KNOB, KNOB), Image.LANCZOS), (0, i * KNOB))
    save(out, "knob_galaxpel70.png")


def pill_image(lit):
    """The 0.2.11 switch: a dark pill, a light-blue dot on the right when on, a grey one on the left when off."""
    S, w, h = 4, 53, 29
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), h * S // 2, fill=BOX + (255,), outline=BEZEL + (255,), width=S)
    r = (h // 2 - 4) * S
    cx = (w - h // 2) * S if lit else (h // 2) * S
    d.ellipse((cx - r, h * S // 2 - r, cx + r, h * S // 2 + r), fill=(ACCENT_HI if lit else (96, 102, 118)) + (255,))
    return im.resize((w, h), Image.LANCZOS)


def box(d, x0, y0, x1, y1, r=4):
    """A Galaxpel display box: near-black with a darker rim (popup fields, readouts, steppers)."""
    d.rounded_rectangle((x0, y0, x1, y1), r, fill=BOX, outline=BEZEL, width=1)


def key_image(w, h, caption, lit, size=None):
    """A momentary key: a dark box with light print; held = the accent blue, dark print."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 5, fill=ACCENT if lit else BOX, outline=ACCENT_HI if lit else BEZEL, width=1)
    f = F(size or (28 if h >= 56 else 22))   # the BANKS header's big keys print larger
    while f.getlength(caption) > w - 12 and f.size > 12:
        f = F(f.size - 1)
    d.text((w // 2, h // 2 + 1), caption, font=f, fill=DARK_TEXT if lit else INK, anchor="mm")
    return im


def arrow_image(w, h, direction, lit):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy, s = w // 2, h // 2, 9
    tip, base = cx + direction * s * 0.7, cx - direction * s * 0.7
    d.polygon([(tip, cy), (base, cy - s), (base, cy + s)], fill=ACCENT_HI if lit else ACCENT)
    return im


def list_key(w, h, caption, lit, size=20):
    """A pick-list option: a dark box, light print; the current choice = accent fill, dark print."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 4, fill=ACCENT if lit else BOX, outline=ACCENT_HI if lit else BEZEL, width=1)
    f = F(size)
    while f.getlength(caption) > w - 10 and f.size > 12:
        f = F(f.size - 1)
    d.text((w // 2, h // 2 + 1), caption, font=f, fill=DARK_TEXT if lit else INK, anchor="mm")
    return im


CLEAR = "clear.png"


# ---- pages --------------------------------------------------------------------------------------------------------------------
class Page:
    def __init__(self, name, fn, sub=0):
        self.name, self.fn, self.sub = name, fn, sub
        self.kids, self.groups, self.qrows = [], [], []

    def tab(self, bgfile):
        kids = [entry("bg", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": bgfile}, "0 0 1280 628")] + self.kids
        return {"version": 1, "tabName": self.name, "fnKeyIndex": self.fn, "fnKeySubIndex": self.sub,
                "componentDefinition": component(kids, background=bg(hexc(PANEL))), "qlinkBoundsData": self.groups}

    def qgroup(self, rect, keys):
        self.groups.append("%d %d %d %d" % (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]))
        self.qrows.append(keys)


def button(kids, key, b, on, off, bid=1, n=1, name=None, ind=None):
    kids.append(entry(name or key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": bid, "numButtonsInGroup": n,
                                              "handleName": "Data", "gestureBehaviour": GESTURE}, b, remap=P(key), ind=ind))


PICK_DEFS = {}


def pick_panel(key, opts, cx, cy, ind=None):
    """A drawn pick-list for the choice `key`: a panel with one radio Button per option (text baked in) and a close key, shown only while
    ui_open == its popup index + 1. Shared per option list. Placed near its field, kept on the page; columns grow to fit the height."""
    n = POPUPS.index(key)
    hdr, gap = 44, 4
    ch = 40 if len(opts) <= 40 else 34 if len(opts) <= 90 else 30
    rows_max = (612 - hdr - 12) // (ch + gap)
    cols = max(1, -(-len(opts) // rows_max))
    cols = max(cols, 3) if len(opts) > 14 else cols
    rows = -(-len(opts) // cols)
    cw = 220 if cols == 1 else max(110, min(200, (1260 - 16) // cols - gap))
    pw, ph = cols * (cw + gap) + gap + 12, hdr + rows * (ch + gap) + gap + 8
    ck = "list_%d_%s" % (len(opts), hashlib.md5("|".join(opts).encode()).hexdigest()[:8])
    if ck not in PICK_DEFS:
        im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, pw - 1, ph - 1), 8, fill=(34, 39, 51), outline=ACCENT, width=2)
        d.text((16, hdr // 2 + 1), "SELECT", font=F(26), fill=ACCENT, anchor="lm")
        kids = [entry("panel", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": save(im, ck + "_bg.png")}, "0 0 %d %d" % (pw, ph))]
        for i, o in enumerate(opts):
            r, c = i % rows, i // rows                 # down the columns
            on = save(list_key(cw, ch, o, True), "%s_%d_on.png" % (ck, i))
            off = save(list_key(cw, ch, o, False), "%s_%d_off.png" % (ck, i))
            kids.append(entry("opt %d" % i, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": i, "numButtonsInGroup": len(opts),
                                                        "handleName": "Data", "gestureBehaviour": GESTURE},
                              "%d %d %d %d" % (8 + gap + c * (cw + gap), hdr + r * (ch + gap), cw, ch)))
        xon = save(key_image(56, 34, "X", True), "x_on.png")
        xoff = save(key_image(56, 34, "X", False), "x_off.png")
        kids.append(entry("close", "Button", {"version": 2, "onImage": xon, "offImage": xoff, "buttonId": 0, "numButtonsInGroup": UI_STEPS,
                                              "handleName": "Data", "gestureBehaviour": GESTURE}, "%d 5 56 34" % (pw - 66), remap=P("ui_open")))
        PICK_DEFS[ck] = (pw, ph, component(kids))
    pw, ph, _ = PICK_DEFS[ck]
    x = min(max(4, cx - pw // 2), 1276 - pw)
    y = min(max(4, cy - 30), 624 - ph)
    return entry("list " + key, ck, {"version": 1, "handleName": "Data"}, "%d %d %d %d" % (x, y, pw, ph), remap=P(key),
                 ind=["IndexedEnabling/%d/%d/Parameter %d" % (n + 1, UI_STEPS, UI_INDEX)] + (ind or []))


def parse_layout():
    tabs, order, cur = {}, [], None
    for line in open(os.path.join(ROOT, "vst", "layout.conf")):
        line = line.strip()
        m = re.match(r"\[tab (.+)\]", line)
        if m:
            cur = tabs.setdefault(m.group(1), {"items": [], "q": [], "art": []})
            order.append(m.group(1))
            continue
        if not cur or not line or line.startswith("#"):
            continue
        if line.startswith("qlinks"):
            cur["q"].append([k.strip() for k in line.split("=", 1)[1].split(",")])
            continue
        kind, rest = line.split(None, 1)
        attrs = {k: v.strip('"') for k, v in re.findall(r'(\w+)=("[^"]*"|\S+)', rest)}
        if kind == "art":
            cur["art"].append(attrs)
        else:
            cur["items"].append((kind, attrs))
    return tabs, order


def when_ind(a):
    """when=rom_bc:Yes -> shown only with a Virus B or C ROM"""
    w = a.get("when")
    if not w:
        return None
    k, v = w.split(":")
    assert k == "rom_bc", w
    return ["IndexedEnabling/%d/2/Parameter %d" % (PARAMS[k]["options"].index(v), ROM_BC)]


def stepper(d, kids, cx, cy, w, h, get, prev, nxt, ind=None):
    """A display box with an arrow key either side (BANK, PRESET, PAGE); a bank / preset name also steps with the wheel."""
    aw = 40
    box(d, cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)
    kids.append(label("%d %d %d %d" % (cx - w // 2 + aw, cy - h // 2, w - 2 * aw, h), get, 24, hexc(DISPLAY_INK), ind=ind))
    if get in FIELD_KEY:
        fw = w - 2 * aw
        FIELDS.add((fw, h))
        kids.append(entry(FIELD_KEY[get] + " field", "field%dx%d" % (fw, h), {"version": 1, "handleName": "Data"},
                          "%d %d %d %d" % (cx - w // 2 + aw, cy - h // 2, fw, h), remap=P(FIELD_KEY[get]), focus="Yes", ind=ind))
    for k, bx, dr in ((prev, cx - w // 2, -1), (nxt, cx + w // 2 - aw, 1)):
        button(kids, k, "%d %d %d %d" % (bx, cy - h // 2, aw, h), save(arrow_image(aw, h, dr, True), "arrow_%d_%d_on.png" % (dr, h)),
               save(arrow_image(aw, h, dr, False), "arrow_%d_%d_off.png" % (dr, h)), ind=ind)


def tiles(art, kids, a):
    """A list of tiles (bank_slot_N, patch_slot_N): the name as a Value label UNDER a transparent Button (a label on top would swallow the
    tap); the lit tile is a translucent accent frame, so the name stays readable (MS-2000R's lesson)."""
    x, y, w, h = int(a["x"]), int(a["y"]) - 86, int(a["w"]), int(a["h"])
    cols, rows, gap, th = int(a["cols"]), int(a["rows"]), int(a["gap"]), int(a["th"])
    tw = (w - (cols - 1) * gap) // cols
    layer = Image.new("RGBA", art.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    on = "tile_on_%dx%d.png" % (tw, th)
    if not os.path.exists(os.path.join(OUT, on)):
        im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, tw - 1, th - 1), 4, fill=ACCENT + (70,), outline=ACCENT_HI + (255,), width=2)
        save(im, on)
    for i in range(cols * rows):
        c, r = (i // rows, i % rows) if a.get("order") == "cols" else (i % cols, i // cols)
        tx, ty = x + c * (tw + gap), y + r * (th + gap)
        ld.rounded_rectangle((tx, ty, tx + tw - 1, ty + th - 1), 4, fill=BOX + (255,), outline=BEZEL + (255,), width=1)
        key = "%s_%d" % (a["key"], i + 1)
        kids.append(label("%d %d %d %d" % (tx + 10, ty, tw - 16, th), key, 24 if th >= 48 else 22 if th >= 34 else 19, hexc(INK), "left verticallyCentred"))
        button(kids, key, "%d %d %d %d" % (tx, ty, tw, th), on, CLEAR, name=key + " tile")
    art.alpha_composite(layer)


# Keys that are not in 0.2.11's layout: RANDOM on PLAY between PANIC and INIT PATCH
EXTRA_KEYS = {"PLAY": [("random_patch", "RANDOM", 182, 236, 104, 44)], "BANKS": [("random_patch", "RANDOM", 932, 126, 128, 58)]}
# 0.2.11's BANKS header had the preset field over the bank field's right arrow (240..800 over 25..275): start it after the bank field
FIX = {}


def layout_tab(name, fn, spec):
    """One printed page at the layout.conf positions (y - 86): the Galaxpel art, then the widgets."""
    art = Image.new("RGBA", (1280, 628), PANEL + (255,))
    kids, panels, pos = [], [], {}
    for a in spec["art"]:
        im = Image.open(os.path.join(VST_IMG, os.path.basename(a["file"]))).convert("RGBA")
        x, y = int(a["x"]), int(a["y"]) - 86
        if a.get("when"):   # conditional art (MOD's B/C-only slots 4-6) is its own Image widget, not page art
            kids.append(entry("art " + a["file"], "Image", {"version": 2, "imageType": "Regular", "colour": "0",
                                                            "image": save(im.convert("RGB"), "art_" + re.sub(r"[^a-z0-9]+", "_", os.path.basename(a["file"]).lower()[:-4]) + ".png")},
                              "%d %d %d %d" % (x, y, im.width, im.height), ind=when_ind(a)))
        else:
            art.alpha_composite(im, (x, y))
    d = ImageDraw.Draw(art)
    for kind, a in spec["items"]:
        key = a.get("key")
        a = dict(a, **FIX.get((name, a.get("get")), {}))
        ind = when_ind(a)
        if kind == "list":
            tiles(art, kids, a)
            d = ImageDraw.Draw(art)
            continue
        cx, cy = int(a["cx"]), int(a["cy"]) - 86
        if kind == "knob":
            assert int(a.get("r", 30)) == 30, a
            kids.append(entry(key, "gknob", {"version": 1, "handleName": "Data"}, "%d %d %d %d" % (cx - KW // 2, cy - 35, KW, KH),
                              remap=P(key), focus="Yes", ind=ind))
            pos[key] = (cx - KW // 2 + 2, cy - 39, cx + KW // 2 - 2, cy + 79)   # knob to value: rows can be 120 px apart (OSC 2 / FM)
        elif kind == "toggle":
            kids.append(entry(key, "gtoggle", {"version": 1, "handleName": "Data"}, "%d %d 53 37" % (cx - 26, cy - 18), remap=P(key), focus="Yes", ind=ind))
            pos[key] = (cx - 50, cy - 26, cx + 50, cy + 40)        # the caption under the switch is in the frame
        elif kind == "popup":
            w, h = int(a["w"]), int(a["h"])
            x0, y0 = cx - w // 2, cy - h // 2
            if ind:   # a conditional field draws its box as an Image widget
                im = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
                box(ImageDraw.Draw(im), 0, 0, w, h)
                kids.append(entry(key + " box", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": save(im, "popbox_%dx%d.png" % (w, h))},
                                  "%d %d %d %d" % (x0, y0, w + 1, h + 1), ind=ind))
            else:
                box(d, x0, y0, x0 + w, y0 + h)
            tri = "poptri.png"
            if not os.path.exists(os.path.join(OUT, tri)):
                ti = Image.new("RGBA", (18, 12), (0, 0, 0, 0))
                ImageDraw.Draw(ti).polygon([(0, 1), (17, 1), (8, 11)], fill=ACCENT + (255,))
                save(ti, tri)
            kids.append(entry(key + " tri", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": tri},
                              "%d %d 18 12" % (x0 + w - 26, cy - 6), ind=ind))
            kids.append(label("%d %d %d %d" % (x0 + 6, y0, w - 34, h), key, 22, hexc(DISPLAY_INK), ind=ind))
            button(kids, "ui_open", "%d %d %d %d" % (x0, y0, w, h), CLEAR, CLEAR, bid=POPUPS.index(key) + 1, n=UI_STEPS, name=key + " field", ind=ind)
            panels.append(pick_panel(key, PARAMS[key]["options"], cx, cy, ind))
            pos[key] = (x0 - 4, y0 - 6, x0 + w + 4, y0 + h + 30)   # the caption under the field is in the frame
        elif kind == "button":
            w, h = int(a.get("w", 200)), int(a.get("h", 44))
            button(kids, key, "%d %d %d %d" % (cx - w // 2, cy - h // 2, w, h), save(key_image(w, h, a["label"], True), "key_%s_on.png" % key),
                   save(key_image(w, h, a["label"], False), "key_%s_off.png" % key), ind=ind)
        elif kind == "readout":
            w, h = int(a["w"]), int(a["h"])
            if a.get("box") != "0":   # box=0: a line of the PLAY page's display, printed straight on its glass
                box(d, cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)
            just = "left verticallyCentred" if a.get("align") == "left" else "horizontallyCentred verticallyCentred"
            kids.append(label("%d %d %d %d" % (cx - w // 2 + 6, cy - h // 2, w - 12, h), key, int(a.get("fs", 22)), hexc(DISPLAY_INK), just, ind=ind))
        elif kind == "stepper":
            w, h = int(a["w"]), int(a["h"])
            stepper(d, kids, cx, cy, w, h, a["get"], a["prev"], a["next"], ind)
            pos[key] = (cx - w // 2 - 4, cy - h // 2 - 4, cx + w // 2 + 4, cy + h // 2 + 4)
            if a["get"] in FIELD_KEY:
                pos[FIELD_KEY[a["get"]]] = pos[key]
            for k in (a["prev"], a["next"]):
                pos[k] = pos[key]
    for key, cap, cx, cy, w, h in EXTRA_KEYS.get(name, []):
        cy -= 86
        button(kids, key, "%d %d %d %d" % (cx - w // 2, cy - h // 2, w, h), save(key_image(w, h, cap, True), "key_%s_%dx%d_on.png" % (key, w, h)),
               save(key_image(w, h, cap, False), "key_%s_%dx%d_off.png" % (key, w, h)))
    pages = []
    for sub, bl in enumerate(sub_tabs(name, spec, pos)):
        p = Page(name, fn, sub)
        p.kids = kids + panels
        if any(k == "button" and a.get("key") == "fav_save" for k, a in spec["items"]):
            keyboard(p.kids)           # +FAV opens the naming keyboard: on top of everything on this page
        for keys, rect in bl:
            p.qgroup(rect, keys)
        check_frames(p)
        pages.append(p)
    return pages, art.convert("RGB")


# Q-Link blocks where the 1.x sets mix rows (their frames would overlap): one row of up to four per block, sub-tabs where a page has more
# than four blocks (same art, other frames). tab -> [sub-tab: [block: keys]]
BLOCKS = {
    "ENV": [[["flt_attack", "flt_decay", "flt_sustain", "flt_sustain_time"], ["flt_release"],
             ["amp_attack", "amp_decay", "amp_sustain", "amp_sustain_time"], ["amp_release"]]],
    "LFO 1+2": [[["lfo1_rate", "lfo1_keyfollow", "lfo1_symmetry", "lfo1_keytrigger"], ["osc1_lfo1_amount", "osc2_lfo1_amount", "pw_lfo1_amount"],
                 ["reso_lfo1_amount", "filtgain_lfo1_amount", "lfo1_assign_amount"]],
                [["lfo2_rate", "lfo2_keyfollow", "lfo2_symmetry", "lfo2_keytrigger"], ["cutoff1_lfo2_amount", "cutoff2_lfo2_amount", "shape_lfo2_amount"],
                 ["fm_lfo2_amount", "pan_lfo2_amount", "lfo2_assign_amount"]]],
    "FX 1": [[["distortion_intensity", "bass_intensity", "bass_tune", "punch_intensity"], ["phaser_rate", "phaser_frequency", "phaser_depth", "phaser_feedback"],
              ["phaser_spread", "phaser_mix"]],
             [["chorus_rate", "chorus_depth", "chorus_feedback", "chorus_delay"], ["chorus_mix"]]],
    "FX 2": [[["low_eq_gain", "low_eq_freq", "mid_eq_gain", "mid_eq_freq"], ["mid_eq_q", "high_eq_gain", "high_eq_freq"],
              ["effect_send", "delay_time", "delay_feedback", "delay_color"], ["delay_rate_rev_decay", "delay_depth"]]],
}


def frame(ks, pos):
    rects = [pos[k] for k in ks]
    r = (min(x[0] for x in rects), min(x[1] for x in rects), max(x[2] for x in rects), max(x[3] for x in rects))
    return (max(2, r[0]), max(2, r[1]), min(1278, r[2]), min(626, r[3]))


def sub_tabs(name, spec, pos):
    """[[(keys, rect)] per sub-tab]: BLOCKS where given, else the layout's 16-key set as four blocks of four."""
    if name in BLOCKS:
        return [[(ks, frame(ks, pos)) for ks in sub] for sub in BLOCKS[name]]
    return [blocks(spec, pos)]


def blocks(spec, pos):
    """The 1.x Q-Link set (16 keys: four of four) as blocks: each block framed round its controls. A stepper's arrows and its value share
    one frame (BANKS: PAGE < > beside PRESET / BANK)."""
    out = []
    for line in spec["q"]:
        for i in range(0, len(line), 4):
            ks = [k for k in line[i:i + 4] if k != "-" and k in pos]
            if not ks:
                continue
            out.append((ks, frame(ks, pos)))
    assert len(out) <= 4, spec["q"]
    return out


def check_frames(p):
    rs = [[int(v) for v in g.split()] for g in p.groups]
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                raise SystemExit("%s/%d: Q-Link frames %d and %d overlap (%s / %s)" % (p.name, p.sub + 1, i + 1, j + 1, p.qrows[i], p.qrows[j]))
                print("note: %s Q-Link frames %d and %d overlap (%s / %s)" % (p.name, i + 1, j + 1, p.qrows[i], p.qrows[j]))


KB_ROWS = [("1234567890", ["kb_bksp"]), ("QWERTYUIOP", []), ("ASDFGHJKL-", []), ("ZXCVBNM", ["kb_space"])]


def kb_cap(w, h, text, lit):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 3, w - 1, h - 1), 7, fill=BEZEL + (255,))
    d.rounded_rectangle((0, 3 if lit else 0, w - 1, h - (1 if lit else 5)), 7, fill=(ACCENT if lit else BOX) + (255,), outline=ACCENT + (255,), width=2)
    f = F(32)
    while f.size > 14 and f.getlength(text) > w - 12:
        f = F(f.size - 1)
    d.text((w // 2, (h - 2) // 2 + (2 if lit else 0)), text, font=f, fill=(DARK_TEXT if lit else INK) + (255,), anchor="mm")
    return im


def keyboard(kids):
    """The naming keyboard for +FAV (Vavra's / Profit-5's): a full-page panel, the name being typed, 42 keys; shown while kb_open = 1."""
    ind = ["IndexedEnabling/1/2/Parameter %d" % LOCK.index("kb_open")]
    im = Image.new("RGB", (1280, 628), PANEL)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 8, 1260, 620), 12, fill=(34, 39, 51), outline=ACCENT, width=2)
    d.text((52, 52), "FAVOURITE NAME", font=F(30), fill=ACCENT, anchor="lm")
    box(d, 300, 24, 1232, 80, 6)
    max_chars = int(re.search(r"kFavNameMax = (\d+)", open(os.path.join(ROOT, "src", "params_gen.h")).read()).group(1))
    d.text((1218, 52), "MAX %d CHARACTERS" % max_chars, font=F(20), fill=DIM, anchor="rm")
    kids.append(entry("kb panel", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": save(im, "kb_panel.png")},
                      "0 0 1280 628", ind=ind))
    kids.append(entry("kb name", "Label", {"version": 1, "textStyle": text_style(42, hexc(DISPLAY_INK), "left verticallyCentred", "Bold"),
                                           "type": "Value", "handleName": "Data"}, "316 24 760 56", P("fav_name"), ind=ind))
    kw, kh, gap, x0, y0 = 98, 84, 8, 64, 100

    def kbkey(k, cap, x, y, w):
        slug = "c%d" % ord(cap) if len(cap) == 1 else cap.lower()   # one character: a unique name on the case-insensitive drive
        on = save(kb_cap(w, kh, cap, True), "kb_%s_%d_on.png" % (slug, w))
        off = save(kb_cap(w, kh, cap, False), "kb_%s_%d_off.png" % (slug, w))
        kids.append(entry(k, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                        "handleName": "Data", "gestureBehaviour": GESTURE}, "%d %d %d %d" % (x, y, w, kh), remap=P(k), ind=ind))
    for r, (chars, extra) in enumerate(KB_ROWS):
        y = y0 + r * (kh + gap)
        x = x0 + r * 30
        for c in chars:
            kbkey("kb_" + ("dash" if c == "-" else c.lower()), c, x, y, kw)
            x += kw + gap
        for k in extra:
            kbkey(k, {"kb_bksp": "DELETE", "kb_space": "SPACE"}[k], x, y, 1216 - x)
    y = y0 + 4 * (kh + gap)
    kbkey("kb_shift", "SHIFT", x0, y, 220)
    kbkey("kb_cancel", "CANCEL", 640 - 130, y, 260)
    kbkey("kb_save", "SAVE", 1216 - 260, y, 260)


def qlinks_for(pages):
    maps = []
    for p in pages:
        q = {"Q-Link %d" % n: -1 for n in range(1, 17)}
        shapes = [int(g.split()[3]) > int(g.split()[2]) for g in p.groups[:4]]
        column = bool(shapes) and all(shapes)   # all blocks taller than wide: bank by columns
        for gi, keys in enumerate(p.qrows[:4]):
            for i, key in enumerate(keys):
                q["Q-Link %d" % ((13 + gi - 4 * i) if column else (13 - 4 * gi + i))] = PI(key)
        maps.append({"Tab": p.fn + 1, "SubTab": p.sub + 1, "Bank Direction": "Column" if column else "RowTopDown", "Q-Links": q})
    return {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
            "Screen Mode Q-Links": {"version": 4, "map": maps}, "Program Mode Q-Links": {"Q-Link %d" % n: -1 for n in range(1, 17)}}


# ---- offline preview: compose a tab the way the MPC draws it --------------------------------------------------------------
SAMPLE = {"preset_name": "AutoBendBC", "bank_name": "Bank A", "loading_status": "Ready: 6 banks of 128",
          "engine_stats": "DROPOUTS 0   CPU 31%", "patch_page_text": "PAGE 1 / 4", "bank_page_text": "1 / 6",
          "rom_name": "Access Virus C (am29f040b_6v6).BIN", "fav_name": "My Pad_"}


def sample_text(key):
    if key in SAMPLE:
        return SAMPLE[key]
    if key.startswith("patch_slot_"):
        return "%03d Patch %s" % (int(key[11:]), key[11:])
    if key.startswith("bank_slot_"):
        n = int(key[10:])
        return "BANK %s" % "ABCDEF"[n - 1] if n <= 6 else "Pads/User %02d" % n
    p = PARAMS.get(key, {})
    if "options" in p:
        return p["options"][p["options"].index(p["default"]) if isinstance(p["default"], str) else int(p["default"])]
    return str(p.get("default", ""))


def visible(e, open_list, keyboard, bc):
    for h in e["bounds"].get("additionalInvalidatingHandles", []):
        i, n, par = re.match(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)", h).groups()
        par = int(par)
        cur = open_list or 0 if par == UI_INDEX else (1 if keyboard else 0) if par == LOCK.index("kb_open") else (1 if bc else 0) if par == ROM_BC else None
        if cur is not None and int(i) != cur:
            return False
    return True


def preview(pages, arts, defs, open_list=None, suffix="", keyboard=False, bc=True):
    os.makedirs(PREVIEW, exist_ok=True)
    for p in pages:
        im = Image.open(os.path.join(OUT, arts[p.name])).convert("RGBA")
        d = ImageDraw.Draw(im)

        def draw(e, ox=0, oy=0):
            cd = e["componentData"]
            x, y, w, h = [int(float(v)) for v in e["bounds"]["bounds"].split()]
            x, y = x + ox, y + oy
            if cd["type"] == "Image":
                im.alpha_composite(Image.open(os.path.join(OUT, cd["data"]["image"])).convert("RGBA"), (x, y))
            elif cd["type"] == "Knob" and cd["data"].get("knobType") == "FilmStrip":
                st = Image.open(os.path.join(OUT, cd["data"]["filmStrip"]))
                im.alpha_composite(st.crop((0, w * 60, w, w * 61)).convert("RGBA"), (x, y))
            elif cd["type"] == "Label":
                m = e["handle remapping"]["map"]
                key = LOCK[int(m[0]["value"].split()[1])] if m else cur_key[0]
                ts = cd["data"]["textStyle"]
                cen = "horizontallyCentred" in ts["justification"]
                col = tuple(int(ts["colour"][i:i + 2], 16) for i in (2, 4, 6))
                f, s = F(int(ts["font"]["height"] * TUI_PX * 1.25), TIT), sample_text(key)
                if f.getlength(s) > w:                     # the MPC cuts a label at its bounds with an ellipsis
                    while s and f.getlength(s + "...") > w:
                        s = s[:-1]
                    s = s.rstrip() + "..."
                d.text((x + w / 2 if cen else x + 2, y + h / 2), s, font=f, fill=col, anchor="mm" if cen else "lm")
            elif cd["type"] == "Button":
                img = cd["data"]["onImage"] if cd["name"] in ("bank_slot_2 tile", "patch_slot_3 tile") else cd["data"]["offImage"]
                if img != CLEAR:
                    im.alpha_composite(Image.open(os.path.join(OUT, img)).convert("RGBA"), (x, y))
            elif cd["type"] in defs:
                m = e["handle remapping"]["map"]
                cur_key[0] = LOCK[int(m[0]["value"].split()[1])] if m and m[0]["value"].split()[1] != str(UI_INDEX) else cur_key[0]
                for sub in defs[cd["type"]]["componentsData"]:
                    if sub["componentData"]["type"] != "Focus":
                        draw(sub, x, y)
        cur_key = [""]
        for e in p.kids:
            if visible(e, open_list, keyboard, bc):
                draw(e)
        for g in p.groups:
            gx, gy, gw, gh = [int(v) for v in g.split()]
            d.rectangle((gx, gy, gx + gw, gy + gh), outline=(255, 160, 40, 220), width=2)
        name = re.sub(r"[^a-z0-9]+", "_", p.name.lower()).strip("_") + ("_sub%d" % (p.sub + 1) if p.sub else "")
        im.convert("RGB").save(os.path.join(PREVIEW, "%s%s.png" % (name, suffix)))


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    save(Image.new("RGBA", (8, 8), (0, 0, 0, 0)), CLEAR)
    knob_strip()
    save(pill_image(True), "pill_on.png")
    save(pill_image(False), "pill_off.png")
    spec, order = parse_layout()
    pages, arts = [], {}
    for fn, name in enumerate(order):
        ps, art = layout_tab(name, fn, spec[name])
        arts[name] = save(art, "bg_%s.png" % re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))
        pages += ps
    tabs = [p.tab(arts[p.name]) for p in pages]
    repl = [{"key": P(k), "value": PARAMS[k]["options"]} for k in POPUPS] + [{"key": P("rom_bc"), "value": PARAMS["rom_bc"]["options"]}]
    defs = definitions() + [{"key": k, "value": v[2]} for k, v in PICK_DEFS.items()]
    tui = {"pageData": {"version": 1, "componentDefinitions": {"version": 2, "importFiles": [], "localComponentDefinitions": defs},
                        "replacementStrings": repl, "info": {"version": 1, "type": "CompleteDescription"}, "tabs": tabs}}
    open(os.path.join(OUT, "TUI.json"), "w").write(dump(tui) + "\n")
    open(os.path.join(OUT, "Q-Links.json"), "w").write(dump(qlinks_for(pages)) + "\n")
    bad = [f for f in os.listdir(OUT) if re.search(r'[<>:"/\\|?*]', f)]
    assert not bad, "file names that exFAT rejects: %s" % bad
    lower = {}
    for f in os.listdir(OUT):
        assert f.lower() not in lower, "names that clash on a case-insensitive drive: %s %s" % (f, lower[f.lower()])
        lower[f.lower()] = f
    assert "object at" not in open(os.path.join(OUT, "TUI.json")).read()
    unbound = [k for k in PARAMS if PARAMS[k].get("display") != "string" and not PARAMS[k].get("momentary") and "_slot_" not in k
               and not any(k in p.qrows[i] for p in pages for i in range(len(p.qrows)))]
    if unbound:
        print("on no Q-Link (%d): %s" % (len(unbound), " ".join(unbound)))
    if "--preview" in sys.argv:
        dd = {x["key"]: x["value"] for x in defs}
        preview(pages, arts, dd)
        preview([p for p in pages if p.name == "OSC"], arts, dd, open_list=POPUPS.index("osc1_wave_select") + 1, suffix="_list")
        preview([p for p in pages if p.name == "MOD"], arts, dd, suffix="_virus_a", bc=False)
        preview([p for p in pages if p.name == "BANKS"], arts, dd, keyboard=True, suffix="_keyboard")
    print("wrote", OUT, "-", len(tabs), "tabs,", len(os.listdir(OUT)), "files,", len(PICK_DEFS), "pick-lists")


if __name__ == "__main__":
    main()
