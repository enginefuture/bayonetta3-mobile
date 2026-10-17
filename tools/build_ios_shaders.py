#!/usr/bin/env python3
"""Compile observed shaders for iphoneos using the frozen, Mac-tested chain."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'third_party/blade2-mobile/dm/gfx/tools'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=int,default=8)
    a=p.parse_args();w=ROOT/'work';s=w/'shaders'
    keys=sorted(set((s/'used.txt').read_text().split()))
    if not keys:p.exit(1,'No observed native shaders\n')
    env=dict(os.environ,DM_ROOT=str(w),DM_SHADER_DIR=str(s),PAIRS=str(s/'shader_pairs.tsv'),
             XLATE=str(w/'build/gfx/dmsh_xlate/dmsh_xlate'),DOTNET_ROOT=str(w/'toolchains/dotnet'),
             IOSOUT=str(s/'ios'),J=str(a.jobs),PATH=str(w/'toolchains/bin')+os.pathsep+os.environ['PATH'])
    subprocess.run([sys.executable,str(T/'dmsh_chain.py'),'--check-tools'],env=env,check=True)
    def version():return subprocess.check_output([sys.executable,str(T/'dmsh_chain.py')],env=env,text=True).strip()
    chain=version();capture=json.loads((w/'shpack/capture_report.json').read_text())
    unsupported={r['key'] for r in capture['unsupported']}
    if unsupported.intersection(keys):p.exit(1,'Observed tessellation stages remain unsupported\n')
    # Preserve the validated macOS libraries and their full-build receipt.
    cache=w/'build/ios-shader-build'
    (s/'ios-used-snapshot.txt').write_text('\n'.join(keys)+'\n')
    subprocess.run([sys.executable,str(T/'dmsh_build.py'),str(w/'shpack'),str(cache),*keys],env=env,check=True)
    if version()!=chain:p.exit(1,'Frozen shader inputs changed during iOS compilation\n')
    results=json.loads((cache/('b-'+chain)/'_b_build.json').read_text())
    if any(r['st']!='ok' for r in results):p.exit(1,'iOS shader compilation failed; inspect _b_build.json\n')
    target=s/'ios'/('b-'+chain)
    if any(not(target/(k+'_b.metallib')).is_file() for k in keys):p.exit(1,'Incomplete iphoneos library set\n')
    (s/'ios-build.json').write_text(json.dumps({'chain':chain,'platform':'iphoneos','observed':len(keys),
        'keys':keys,'scope':'Observed Mac path only; device compatibility and later scenes not verified'},indent=2)+'\n')
    print(f'iphoneos: {len(keys)} observed shaders built for {chain}; device runtime not yet verified')

if __name__=='__main__':main()
