#!/usr/bin/env python3
"""Read the parameter table of the released 1.x wrapper build out of its osirus.so (aarch64), the frozen truth for params.lock.

The wrapper's param_t of that build was 112 bytes, key pointer first, min/max/def floats at +24 and nopts at +36; the table is the run
of R_AARCH64_RELATIVE relocations that starts with "bank_index". Prints one line per parameter: key, min, max, default, option count.
    tools/released_params.py <osirus.so> [count]       (count: 300 for Osirus 0.2.11; past it the walk runs into option strings)
"""
import struct, sys

STRIDE = 112
d = open(sys.argv[1], 'rb').read()
count = int(sys.argv[2]) if len(sys.argv) > 2 else 300
shoff, = struct.unpack_from('<Q', d, 0x28)
shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3a)
secs = [struct.unpack_from('<IIQQQQIIQQ', d, shoff + i * shentsize) for i in range(shnum)]
strtab = secs[shstrndx]


def name(s):
    return d[strtab[4] + s[0]:d.index(b'\0', strtab[4] + s[0])].decode()


def v2o(a):
    for s in secs:
        if s[1] != 8 and s[3] and s[3] <= a < s[3] + s[5]:
            return s[4] + a - s[3]


rel = {}
for s in secs:
    if name(s) == '.rela.dyn':
        for i in range(s[5] // 24):
            off, info, add = struct.unpack_from('<QQq', d, s[4] + i * 24)
            if info & 0xffffffff == 1027:
                rel[off] = add


def cstr(a):
    o = v2o(a)
    return d[o:d.index(b'\0', o)].decode('latin1') if o is not None else None


start = next(off for off, add in sorted(rel.items()) if cstr(add) == 'bank_index' and off + 8 in rel)
for i in range(count):
    o = start + i * STRIDE
    mn, mx, df, nopts = struct.unpack_from('<fffi', d, v2o(o + 24))
    print("%s\t%g\t%g\t%g\t%d" % (cstr(rel[o]), mn, mx, df, nopts))
