#!/usr/bin/env python3
"""Compile the checksummed Mac-tested shader corpus for a physical iOS device.

Translation and reflection stay identical. Only Apple's target compiler changes;
Mac metallibs are never copied into the iPhone bundle. All outputs remain private.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DM = ROOT/'third_party/blade2-mobile/dm'
sys.path[:0] = [str(DM/'gfx/tools'), str(DM/'ios/tools')]
import dmsh_fetch
import ios_metal


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs', type=int, default=6)
    a = p.parse_args()
    w = ROOT/'work'
    chain = re.search(r'DMSH_CHAIN "(\w+)"', (DM/'gfx/nvn/dmsh_chain.h').read_text())[1]
    source = w/'build/cache/metal_shader_cache'/('b-'+chain)
    manifest = json.loads((source/'_interfaces.json').read_text())
    if manifest['chain'] != chain:
        p.exit(1, 'Mac interface receipt has a different chain\n')
    # Require the exact complete, already validated source/metadata corpus.
    for name, digest in manifest['files'].items():
        if sha(source/name) != digest:
            p.exit(1, f'Mac corpus changed after validation: {name}\n')
    target = w/'shaders/ios'/('b-'+chain)
    target.mkdir(parents=True, exist_ok=True)
    compiler = subprocess.check_output(['xcrun', '-sdk', 'iphoneos', 'metal', '--version'], text=True).strip()
    sdk = subprocess.check_output(['xcrun', '-sdk', 'iphoneos', '--show-sdk-version'], text=True).strip()
    stamp = hashlib.sha256((compiler+sdk+ios_metal.RECORD).encode()).hexdigest()
    jobs = []
    reflection = {}
    for src in sorted(source.glob('*_b.metal')):
        meta = json.loads(src.with_suffix('.json').read_text())
        if meta['chain'] != chain:
            raise ValueError('Reflection chain mismatch: '+src.name)
        reflection[src.stem] = dict(meta, chain_metal=ios_metal.RECORD)
        jobs.append((src.stem, src.read_text()))
        if (source/(src.stem+'f.metallib')).is_file():
            text, info = dmsh_fetch.variant(src.read_text(), meta['bindings'], om_only_ok=True)
            if not text or info != meta.get('fetch'):
                raise ValueError('Fragment variant differs from validated reflection: '+src.name)
            jobs.append((src.stem+'f', text))
    def build(job):
        name, text = job
        src = target/(name+'.metal')
        lib = target/(name+'.metallib')
        receipt = target/(name+'.build.json')
        digest = hashlib.sha256(text.encode()).hexdigest()
        previous = json.loads(receipt.read_text()) if receipt.exists() else {}
        if previous.get('source_sha256') != digest or previous.get('compiler') != stamp or not lib.exists() or previous.get('metallib_sha256') != sha(lib):
            src.write_text(text)
            air = target/(name+'.air')
            temp = target/(name+'.metallib.tmp')
            ios_metal.compile(str(src), str(air), str(temp))
            os.replace(temp, lib)
            air.unlink()
            receipt.write_text(json.dumps({'source_sha256':digest, 'compiler':stamp, 'metallib_sha256':sha(lib)})+'\n')
        if name in reflection:
            (target/(name+'.json')).write_text(json.dumps(reflection[name], indent=2)+'\n')
        return name
    names = []
    with ThreadPoolExecutor(max_workers=a.jobs) as executor:
        for name in executor.map(build, jobs):
            names.append(name)
            if len(names)%100 == 0:
                print(f'iphoneos shaders: {len(names)}/{len(jobs)}', flush=True)
    if re.search(r'DMSH_CHAIN "(\w+)"', (DM/'gfx/nvn/dmsh_chain.h').read_text())[1] != chain:
        raise ValueError('Host chain changed during compilation')
    files = {f.name:sha(f) for name in names for f in (target/(name+'.metallib'),) }
    files.update({name+'.json':sha(target/(name+'.json')) for name in reflection})
    receipt = {'schema':2, 'chain':chain, 'platform':'iphoneos', 'sdk':sdk, 'metal_version':compiler,
               'chain_metal':ios_metal.RECORD, 'base_stages':len(reflection), 'variants':len(names)-len(reflection),
               'source_manifest_sha256':sha(source/'_interfaces.json'), 'files':files,
               'scope':'Complete inventoried ordinary corpus; device execution and later scenes require separate verification.'}
    (w/'shaders/ios-build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'iphoneos: {len(names)} libraries built for {chain}', flush=True)

if __name__ == '__main__':
    main()
