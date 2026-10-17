#!/usr/bin/env python3
"""Generate an embedded iOS host; optionally sign with a local development team."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DM = ROOT/'third_party/blade2-mobile/dm'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=ROOT/'work')
    p.add_argument('--generate-only', action='store_true')
    p.add_argument('--team-id',default='')
    p.add_argument('--bundle-id',default='org.local.bayonetta3mobile')
    p.add_argument('--sign',action='store_true',help='Use Xcode automatic development signing and existing account credentials')
    a = p.parse_args()
    if a.sign and not a.team_id:p.error('--sign requires --team-id')
    work = a.work.resolve()
    ios = ROOT/'platform/ios'
    gen = ios/'Gen'
    if gen.exists():
        gen.rename(ios/('Gen.previous-'+str(time.time_ns())))
    for part in ('dm','msl'):
        (gen/part).mkdir(parents=True,exist_ok=True)
    profile = json.loads((ROOT/'config/bayonetta3-1.2.0.json').read_text())
    mods = profile['runtime_modules']
    out = work/'rewrite'
    receipt=json.loads((work/'verification.json').read_text())
    if not receipt.get('passed') or set(receipt['modules'])!=set(mods):
        p.exit(1,'Complete module rewrite verification required\n')
    for name in mods:
        for suffix in ('patched.bin','fixups.tsv','gates.tsv','sites.tsv','cuts.tsv'):
            if hashlib.sha256((out/f'{name}.{suffix}').read_bytes()).hexdigest()!=receipt['modules'][name][suffix+'_sha256']:
                p.exit(1,f'{name}: rewrite changed after verification\n')
    if a.sign:
        mobile=work/'shaders/ios-build.json'
        if not mobile.is_file():p.exit(1,'Build iphoneos shaders before signing\n')
        info=json.loads(mobile.read_text())
        header=(DM/'gfx/nvn/dmsh_chain.h').read_text()
        if f'"{info["chain"]}"' not in header:p.exit(1,'iphoneos shader chain differs from host header\n')
    for name in mods:
        for suffix in ('patched.bin','fixups.tsv','gates.tsv'):
            if not (out/f'{name}.{suffix}').is_file():
                p.exit(1, f'Missing rewrite output: {name}.{suffix}\n')
    config = subprocess.check_output([sys.executable,DM/'ios/tools/gen_build.py',DM/'host',gen,
                                      'Makefile.bayonetta3','dmhost_bayonetta3'], text=True)
    flags = subprocess.check_output([sys.executable,DM/'ios/tools/gen_embed.py',out,gen/'embed.S',*mods], text=True).strip()
    (gen/'dm.xcconfig').write_text(config+'\nOTHER_LDFLAGS = $(inherited) $(DM_FRAMEWORKS) '+flags+'\n')
    for name in mods:
        for suffix in ('fixups.tsv','gates.tsv','cuts.tsv'):
            src = out/f'{name}.{suffix}'
            if src.exists():
                shutil.copy2(src,gen/'dm'/src.name)
    # Never package another game's shader tables. An empty table permits diagnostics only.
    shaderdir = work/'shaders'
    for name in ('shader_map.tsv','c1_full.tsv'):
        src = shaderdir/name
        if src.is_file():
            shutil.copy2(src,gen/'dm'/name)
        else:
            (gen/'dm'/name).write_text('# Bayonetta 3 shader capture pending\n')
    if (shaderdir/'ios').is_dir():
        shutil.copytree(shaderdir/'ios', gen/'msl',dirs_exist_ok=True)
    env = dict(os.environ, DM_BUNDLE_ID=a.bundle_id, DM_TEAM_ID=a.team_id)
    subprocess.run(['xcodegen','generate','--spec',str(ios/'project.yml')], env=env,check=True,cwd=ios)
    if not a.generate_only:
        log = work/'build-ios.log'
        with log.open('w') as f:
            command=['xcodebuild','-project',str(ios/'Bayonetta3IOS.xcodeproj'),'-scheme','Bayonetta3',
                                    '-configuration','Debug','-destination','generic/platform=iOS',
                                    '-derivedDataPath',str(work/'ios')]
            command+=['-allowProvisioningUpdates'] if a.sign else ['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
            result = subprocess.run(command+['build'],stdout=f,stderr=subprocess.STDOUT,env=env)
        if result.returncode:
            p.exit(result.returncode,f'iOS build failed: {log}\n')
        print(f'{"Development-signed" if a.sign else "Unsigned"} iOS host compiled: {work}/ios/Build/Products/Debug-iphoneos/Bayonetta3.app')
        print('Build only. No device install or on-device gameplay verified.')


if __name__ == '__main__':
    main()
