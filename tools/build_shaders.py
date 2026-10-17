#!/usr/bin/env python3
"""Build Bayonetta-only captured shaders with the pinned local translator."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'third_party/blade2-mobile/dm/gfx/tools'

def snapshot_pairs(source, destination):
    """Freeze effective graphics edges; duplicate samples/compute state are irrelevant."""
    edges=set()
    if source.exists():
        for line in source.read_text().splitlines():
            stages=dict(item.split(':',1) for item in line.split() if ':' in item)
            if '0' not in stages:continue
            for stage in ('1','2'):
                if stage in stages:edges.add(f"0:{stages['0']} {stage}:{stages[stage]}")
    destination.write_text('\n'.join(sorted(edges))+'\n')

def main():
    from shader_interfaces import build_receipt
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=int,default=6)
    p.add_argument('--used-only',action='store_true',help='Build shaders observed by the native submit path')
    a=p.parse_args()
    w=ROOT/'work';shader=w/'shaders';shader.mkdir(exist_ok=True)
    snapshot_pairs(shader/'pairs.tsv',shader/'shader_pairs.tsv')
    if not list((w/'shdump').glob('*.ctl')):p.exit(1,'No game shader captures yet\n')
    bindir=w/'toolchains/bin';bindir.mkdir(parents=True,exist_ok=True)
    cross=bindir/'spirv-cross'
    if not cross.exists():
        existing=shutil.which('spirv-cross')
        if not existing:p.exit(1,'Install spirv-cross or place it at work/toolchains/bin/spirv-cross\n')
        shutil.copy2(existing,cross)
    env=dict(os.environ,DM_ROOT=str(w),DM_SHADER_DIR=str(shader),DM_TEXFACTS=str(shader/'texfacts.tsv'),
             PAIRS=str(shader/'shader_pairs.tsv'),XLATE=str(w/'build/gfx/dmsh_xlate/dmsh_xlate'),
             DOTNET_ROOT=str(w/'toolchains/dotnet'),J=str(a.jobs),
             PATH=str(bindir)+os.pathsep+os.environ['PATH'])
    def run(cmd):subprocess.run([str(x) for x in cmd],env=env,check=True)
    run([sys.executable,T/'dmsh_from_dump.py',w/'shdump',w/'shpack','bayonetta3'])
    capture=json.loads((w/'shpack/capture_report.json').read_text())
    if capture['invalid']:p.exit(1,'Invalid shader captures; rerun the repaired native capture path before compiling\n')
    run([sys.executable,T/'dmsh_chain.py','--update-lock'])
    run([sys.executable,T/'dmsh_chain.py','--header'])
    version=subprocess.check_output([sys.executable,T/'dmsh_chain.py'],env=env,text=True).strip()
    keys=[]
    if a.used_only:
        used=shader/'used.txt'
        if not used.exists():p.exit(1,'No shaders observed at submit yet\n')
        keys=sorted(set(used.read_text().split()))
        if not keys:p.exit(1,'No shaders observed at submit yet\n')
        unsupported={r['key']:r['stage'] for r in capture['unsupported']}
        used_unsupported={k:unsupported[k] for k in keys if k in unsupported}
        if used_unsupported:p.exit(1,f'Used unsupported shader stages: {used_unsupported}\n')
    run([sys.executable,T/'dmsh_build.py',w/'shpack',w/'build/cache/metal_shader_cache',*keys])
    current=subprocess.check_output([sys.executable,T/'dmsh_chain.py'],env=env,text=True).strip()
    if current!=version:p.exit(1,'Shader sources changed while compiling; rebuild this chain before running\n')
    results=json.loads((w/'build/cache/metal_shader_cache'/('b-'+version)/'_b_build.json').read_text())
    failed=[r for r in results if r['st']!='ok']
    if failed:p.exit(1,f"{len(failed)} shader builds failed; see _b_build.json in b-{version}\n")
    run([sys.executable,T/'c1_guard.py',w/'build/cache/metal_shader_cache'/('b-'+version),shader/'c1_full.tsv'])
    interfaces=build_receipt(w/'build/cache/metal_shader_cache'/('b-'+version),version)
    print(f"Complete varying ABI checked: {interfaces['vertices']} vertex / {interfaces['fragments']} fragment libraries, {len(interfaces['required'])} locations")
    print(f"Ordinary shader generation finished; {len(capture['unsupported'])} tessellation stages use the separate build_tessellation.py supplement. Rebuild host before running this chain.")

if __name__=='__main__':main()
