#!/usr/bin/env python3
"""Verify/decompress NSO segments and inventory dynamic imports from local ExeFS."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import lz4.block

ROOT = Path(__file__).resolve().parents[1]


def load_nso(path):
    d = path.read_bytes()
    if len(d) < 256 or d[:4] != b'NSO0':
        raise ValueError(f'Invalid NSO: {path}')
    flags = struct.unpack_from('<I', d, 12)[0]
    segs = [struct.unpack_from('<III', d, 0x10 + i * 16) for i in range(3)]
    bss = struct.unpack_from('<I', d, 0x3c)[0]
    end = max(mo + sz for _, mo, sz in segs)
    if end + bss > 1024 * 1024 * 1024:
        raise ValueError('NSO exceeds 1 GiB analysis budget')
    img = bytearray(end + bss)
    report = dict(name=path.name, sha256=hashlib.sha256(d).hexdigest(), build_id=d[0x40:0x60].hex(),
                  bss_bytes=bss, segments=[])
    for i, (fo, mo, sz) in enumerate(segs):
        stored = struct.unpack_from('<I', d, 0x60 + i * 4)[0] if flags & (1 << i) else sz
        if fo < 256 or fo + stored > len(d):
            raise ValueError('NSO segment outside input')
        raw = d[fo:fo + stored]
        if flags & (1 << i):
            raw = lz4.block.decompress(raw, uncompressed_size=sz)
        digest = hashlib.sha256(raw).digest()
        if len(raw) != sz or (flags & (1 << (i + 3)) and digest != d[0xa0 + i * 32:0xc0 + i * 32]):
            raise ValueError('NSO segment size/hash mismatch')
        img[mo:mo + sz] = raw
        report['segments'].append(dict(name=['text','rodata','data'][i], offset=mo, bytes=sz,
                                       sha256=digest.hex(), header_hash_required=bool(flags & (1 << (i + 3)))))
    # NSO metadata gives exact .dynsym/.dynstr ranges, relative to rodata.
    ro = segs[1][1]
    stro, strs = struct.unpack_from('<II', d, 0x90)
    symo, syms = struct.unpack_from('<II', d, 0x98)
    if ro + stro + strs > end or ro + symo + syms > end or syms % 24:
        raise ValueError('Invalid dynamic symbol metadata')
    strings = img[ro + stro:ro + stro + strs]
    symbols = []
    for off in range(ro + symo, ro + symo + syms, 24):
        no, info, other, ndx, value, size = struct.unpack_from('<IBBHQQ', img, off)
        if no >= len(strings):
            raise ValueError('Symbol name exceeds string table')
        endname = strings.find(0, no)
        if endname < 0:
            raise ValueError('Unterminated symbol')
        name = strings[no:endname].decode('utf-8', errors='replace')
        if name:
            symbols.append(dict(name=name, defined=ndx != 0, value=value, binding=info >> 4))
    report['imports'] = [s['name'] for s in symbols if not s['defined']]
    report['weak_imports'] = [s['name'] for s in symbols if not s['defined'] and s['binding'] == 2]
    report['exports'] = [s['name'] for s in symbols if s['defined'] and s['binding'] in (1,2)]
    report['export_addresses'] = {s['name']:hex(s['value']) for s in symbols if s['defined'] and s['binding'] in (1,2)}
    return report, img


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=ROOT/'work')
    p.add_argument('--exefs', type=Path, help='Override ExeFS location for an extraction still in progress')
    a = p.parse_args()
    out = a.work/'analysis'
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    for src in sorted((a.exefs or a.work/'game/ExeFS').iterdir()):
        if src.name == 'main.npdm' or src.read_bytes()[:4] != b'NSO0':
            continue
        report, img = load_nso(src)
        (out/(src.name+'.img')).write_bytes(img)
        reports.append(report)
        print(f"{src.name}: {report['build_id']} imports={len(report['imports'])} exports={len(report['exports'])}")
    # rtld is inspected separately; the native host replaces it and loads the others.
    runtime = [r for r in reports if r['name'] != 'rtld']
    exports = {n for r in runtime for n in r['exports']}
    imports = {n for r in runtime for n in r['imports']}
    host = ROOT/'third_party/blade2-mobile/dm/host'
    provided = set()
    for src in host.iterdir():
        if src.suffix in ('.c','.m','.h'):
            t = src.read_text(errors='replace')
            provided.update(re.findall(r'HLE(?:_FORCE)?\(\s*"([^"]+)"', t))
            if src.name == 'hle_table.c':
                provided.update(re.findall(r'\bL\((\w+)\)', t))
    unresolved = sorted(imports - exports)
    weak = {n for r in runtime for n in r['weak_imports']}
    coverage = dict(unresolved_by_guest_modules=unresolved,
                    host_name_matches=sorted(set(unresolved)&provided),
                    missing_host_names=sorted(set(unresolved)-provided),
                    unresolved_weak_names=sorted(set(unresolved)&weak),
                    limitation='Source name matches only; not ABI validation or runtime coverage. Preprocessor branches may exclude names.')
    (out/'modules.json').write_text(json.dumps(reports,indent=2)+'\n')
    (out/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    (out/'imports.tsv').write_text('module\tsymbol\tresolution\n'+''.join(
        f"{r['name']}\t{n}\t{'guest' if n in exports else 'host-name-match' if n in provided else 'missing'}\n"
        for r in runtime for n in r['imports']))
    print(f'Guest-external imports: {len(unresolved)}; missing host names: {len(coverage["missing_host_names"])}')


if __name__ == '__main__':
    main()
