#!/usr/bin/env python3
"""Compile the verified tessellation supplement for iphoneos, separately from Mac."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
DM = ROOT/'third_party/blade2-mobile/dm'
sys.path.insert(0, str(DM/'ios/tools'))
import ios_metal

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    w = ROOT/'work'
    chain = re.search(r'DMSH_CHAIN "(\w+)"', (DM/'gfx/nvn/dmsh_chain.h').read_text())[1]
    source = w/'build/cache/tessellation'/chain
    original = json.loads((source/'_tessellation.json').read_text())
    if original['chain'] != chain or original['unsupported']:
        raise ValueError('Complete verified Mac tessellation supplement required')
    for name, digest in original['files'].items():
        if sha(source/name) != digest: raise ValueError('Changed tessellation artifact: '+name)
    target = w/'shaders/ios-tessellation'/chain
    target.mkdir(parents=True, exist_ok=True)
    def build(src):
        name = src.stem
        (target/src.name).write_bytes(src.read_bytes())
        ios_metal.compile(str(target/src.name), str(target/(name+'.air')), str(target/(name+'.metallib')))
        (target/(name+'.air')).unlink()
        meta = json.loads((source/(name+'.json')).read_text())
        meta['chain_metal'] = ios_metal.RECORD
        (target/(name+'.json')).write_text(json.dumps(meta, indent=2)+'\n')
        return name
    with ThreadPoolExecutor(max_workers=6) as executor:
        names = list(executor.map(build, sorted(source.glob('*.metal'))))
    receipt = dict(original, platform='iphoneos', chain_metal=ios_metal.RECORD,
                   metal_version=subprocess.check_output(['xcrun','-sdk','iphoneos','metal','--version'], text=True).strip(),
                   source_receipt_sha256=sha(source/'_tessellation.json'),
                   files={p.name:sha(p) for name in names for p in (target/(name+'.metal'),target/(name+'.json'),target/(name+'.metallib'))})
    (target/'_tessellation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'iphoneos tessellation: {len(names)} libraries / {len(original["pairs"])} observed combinations, {target}')

if __name__ == '__main__': main()
