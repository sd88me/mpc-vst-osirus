#!/usr/bin/env python3
"""Read the control positions of one of gearmulator's Osirus skins (default: Galaxpel, skin/galaxpel/VirusC_Galaxpel.rml, GPL-3.0) and write
pages.json beside it: per page, each control's key (our params.json key, matched on the Virus parameter page+index), its kind and
its box in the page image's own pixels. tools/make_layout.py scales that onto the MPC screen.
    import_galaxpel.py [<skin dir> <rml file> [<parameterDescriptions json>]]    e.g. a Trancy or Hoverland skin folder"""
import sys
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "skin", "galaxpel")
RML = sys.argv[2] if len(sys.argv) > 2 else "VirusC_Galaxpel.rml"
DESC = sys.argv[3] if len(sys.argv) > 3 else os.path.join(SK, "parameterDescriptions_C.json")

desc = open(DESC).read()
by_name = {}
for m in re.finditer(r'\{[^{}]*"page":\s*(\d+)[^{}]*?"index":\s*(\d+)[^{}]*?"name":\s*"([^"]*)"', desc):
    by_name.setdefault(m.group(3).strip(), (int(m.group(1)), int(m.group(2))))
for m in re.finditer(r'\{[^{}]*"page":\s*(\d+)[^{}]*?"name":\s*"([^"]*)"[^{}]*?"index":\s*(\d+)', desc):
    by_name.setdefault(m.group(2).strip(), (int(m.group(1)), int(m.group(3))))

# our table: key -> (page, cc) from the plugin source
src = open(os.path.join(HERE, "..", "src", "dsp", "virus_plugin.cpp")).read()
ours = {}
for m in re.finditer(r'\{"(\w+)",\s*"[^"]*",\s*VIRUS_PAGE_([AB]),\s*(\d+),', src):
    ours[(112 if m.group(2) == "A" else 113, int(m.group(3)))] = m.group(1)

rml = open(os.path.join(SK, RML)).read()
pages = {}
for pid in ("page_osc", "page_lfo", "page_fx", "page_arp"):
    a = rml.index('<img id="%s"' % pid)
    b = rml.find("</img>", a)
    block = rml[a:b]
    src_img = re.search(r'src="([^"]+)"', block).group(1)
    size = re.search(r'width:\s*([\d.]+)dp;\s*height:\s*([\d.]+)dp', block).groups()
    items, missing = [], []
    for m in re.finditer(r'<(knob|combo|button)\b([^>]*)>', block):
        kind, attrs = m.group(1), m.group(2)
        p = re.search(r'\bparam="([^"]*)"', attrs)
        st = re.search(r'left:\s*([\d.]+)dp;\s*top:\s*([\d.]+)dp;\s*width:\s*([\d.]+)dp;\s*height:\s*([\d.]+)dp', attrs)
        if not p or not st:
            continue
        name = p.group(1).strip()
        pi = by_name.get(name)
        key = ours.get(pi) if pi else None
        if not key:
            missing.append(name)
            continue
        x, y, w, h = (float(v) for v in st.groups())
        items.append(dict(kind=kind, key=key, x=x, y=y, w=w, h=h, toggle='isToggle="1"' in attrs))
    pages[pid] = dict(image=src_img, w=float(size[0]), h=float(size[1]), items=items, missing=missing)
    print(pid, len(items), "controls; no key for:", sorted(set(missing)))
json.dump(pages, open(os.path.join(SK, "pages.json"), "w"), indent=1)
