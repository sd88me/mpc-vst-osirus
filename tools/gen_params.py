#!/usr/bin/env python3
"""Write vst/params.json from the parameter table in src/dsp/virus_plugin.cpp (g_params + its opts_* label arrays).

The VST parameter index is the position in this list and saved projects bind to it: the engine's own keys come first,
then the table in source order, and new entries are only ever appended (vst/params.lock, checked by gen_vst.py)."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src", "dsp", "virus_plugin.cpp")
OUT = os.path.join(HERE, "..", "vst", "params.json")

text = open(SRC).read()

opts = {}
for m in re.finditer(r"static const char \*(opts_\w+)\[\] = \{(.*?)\};", text, re.S):
    opts[m.group(1)] = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))

a = text.index("static const virus_param_t g_params[] = {")
b = text.index("};", a)
body = text[a:b]

section = "Other"
rows = []
for line in body.split("\n"):
    c = re.match(r"\s*/\* Page ([AB]): (.*?) \*/", line)
    if c:
        section = c.group(2)
        continue
    m = re.match(r'\s*\{"(\w+)",\s*"([^"]*)",\s*VIRUS_PAGE_([AB]),\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*VIRUS_MODEL_(\w+),\s*(NO_OPTS|OPTS\((\w+)\))\}', line)
    if not m:
        if line.strip().startswith("{\""):
            raise SystemExit("unparsed row: " + line)
        continue
    key, name, page, cc, lo, hi, model, _, arr = m.groups()
    rows.append(dict(key=key, name=name, page=page, cc=int(cc), lo=int(lo), hi=int(hi), model=model, opts=arr, section=section))

params = []
keys_in = {}


def add(p, sec=None):
    params.append(p)
    if sec:
        keys_in.setdefault(sec, []).append(p["key"])


# engine keys first
add(dict(key="bank_index", name="BANK", min=0, max=31, default=0, display="int"), "Browse")
add(dict(key="preset", name="PRESET", min=0, max=127, default=0, display="int"), "Browse")
add(dict(key="bank_name", name="BANK NAME", min=0, max=0, default=0, display="string", poll=True), "Browse")
add(dict(key="preset_name", name="PRESET NAME", min=0, max=0, default=0, display="string", poll=True), "Browse")
add(dict(key="bank_prev", name="BANK -", min=0, max=1, default=0, momentary=True, step_of="bank_index", step_delta=-1), "Browse")
add(dict(key="bank_next", name="BANK +", min=0, max=1, default=0, momentary=True, step_of="bank_index", step_delta=1), "Browse")
add(dict(key="preset_prev", name="PRESET -", min=0, max=1, default=0, momentary=True, step_of="preset", step_delta=-1), "Browse")
add(dict(key="preset_next", name="PRESET +", min=0, max=1, default=0, momentary=True, step_of="preset", step_delta=1), "Browse")
add(dict(key="octave_transpose", name="OCTAVE", min=-4, max=4, default=0, display="int"), "Browse")
add(dict(key="all_notes_off", name="PANIC", min=0, max=1, default=0, momentary=True), "Browse")
add(dict(key="rom_model", name="MODEL", min=0, max=0, default=0, display="string", poll=True), "System")
add(dict(key="rom_name", name="ROM", min=0, max=0, default=0, display="string", poll=True), "System")
add(dict(key="loading_status", name="STATUS", min=0, max=0, default=0, display="string", poll=True), "System")
add(dict(key="rom_index", name="ROM #", min=0, max=7, default=0, display="int"), "System")
add(dict(key="dsp_clock", name="DSP CLOCK %", min=10, max=100, default=100, display="int"), "System")
add(dict(key="gain", name="OUTPUT LEVEL %", min=1, max=100, default=70, display="int"), "System")

SEC_ORDER = []
for r in rows:
    p = dict(key=r["key"], name=r["name"], min=r["lo"], max=r["hi"], default=r["lo"] if r["lo"] > 0 else 0)
    if r["opts"]:
        labels = opts[r["opts"]]
        if r["lo"] != 0 or r["hi"] > len(labels) - 1:
            raise SystemExit("%s: options %s do not span %d..%d" % (r["key"], r["opts"], r["lo"], r["hi"]))
        labels = labels[:r["hi"] + 1]   # arp_clock / delay_clock use the first 18 / 17 labels of the shared list
        p = dict(key=r["key"], name=r["name"], options=labels, default=labels[0])
    else:
        p["display"] = "int"
        if r["lo"] > 0:
            p["default"] = (r["lo"] + r["hi"]) // 2
    if r["model"] != "ALL":
        p["model"] = r["model"]
    params.append(p)
    sec = r["section"] + ("" if r["model"] == "ALL" else "")
    keys_in.setdefault(sec, []).append(r["key"])
    if sec not in SEC_ORDER:
        SEC_ORDER.append(sec)

# BANKS page list tiles (appended last: saved projects bind by index)
for i in range(1, 17):
    add(dict(key="bank_slot_%d" % i, name="BANK %d" % i, min=0, max=1, default=0, momentary=True, display="string", poll=True), "Banks")
for i in range(1, 31):
    add(dict(key="patch_slot_%d" % i, name="PATCH %d" % i, min=0, max=1, default=0, momentary=True, display="string", poll=True), "Banks")
add(dict(key="patch_page_text", name="PAGE", min=0, max=0, default=0, display="string", poll=True), "Banks")
add(dict(key="patch_page_prev", name="PAGE -", min=0, max=1, default=0, momentary=True), "Banks")
add(dict(key="patch_page_next", name="PAGE +", min=0, max=1, default=0, momentary=True), "Banks")

add(dict(key="rom_bc", name="B/C ROM", options=["No", "Yes"], default="No"), "System")
add(dict(key="rom_bc", name="B/C ROM", options=["No", "Yes"], default="No"), "System")
add(dict(key="engine_stats", name="STATS", min=0, max=0, default=0, display="string", poll=True), "System")
add(dict(key="init_patch", name="INIT", min=0, max=1, default=0, momentary=True), "System")
sections = [{"label": "Browse", "keys": keys_in["Browse"]}, {"label": "Banks", "keys": keys_in["Banks"]}, {"label": "System", "keys": keys_in["System"]}]
sections += [{"label": s, "keys": keys_in[s]} for s in SEC_ORDER]
for p in params:
    p.pop("model", None)

json.dump({"name": "Osirus", "params": params, "sections": sections}, open(OUT, "w"), indent=1)
print("params.json: %d params, %d sections" % (len(params), len(sections)))
