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
    p.add_argument('--device',default='',help='Connected device UDID for provisioning registration')
    p.add_argument('--configuration',choices=('Debug','Release'),default='Release')
    p.add_argument('--widescreen', action='store_true', help='Compatibility option: both normal and wide modes are now included in every build')
    a = p.parse_args()
    if a.sign and not a.team_id:p.error('--sign requires --team-id')
    work = a.work.resolve()
    ios = ROOT/'platform/ios'
    gen = ios/'Gen'
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
    mobile_files={};tess_files={}
    if a.sign or (work/'shaders/ios-build.json').exists():
        mobile=work/'shaders/ios-build.json'
        if not mobile.is_file():p.exit(1,'Build iphoneos shaders before signing\n')
        info=json.loads(mobile.read_text())
        header=(DM/'gfx/nvn/dmsh_chain.h').read_text()
        if f'"{info["chain"]}"' not in header:p.exit(1,'iphoneos shader chain differs from host header\n')
        if info.get('schema')!=2 or info.get('platform')!='iphoneos':p.exit(1,'Rebuild the complete iphoneos shader corpus\n')
        mobile_root=work/'shaders/ios'/('b-'+info['chain'])
        mobile_files=info['files']
        tess_root=work/'shaders/ios-tessellation'/info['chain']
        tess=json.loads((tess_root/'_tessellation.json').read_text())
        if tess.get('platform')!='iphoneos' or tess.get('chain')!=info['chain'] or tess['unsupported']:
            p.exit(1,'Complete iphoneos tessellation supplement required\n')
        tess_files={k:v for k,v in tess['files'].items() if k.endswith(('.json','.metallib'))}
        for directory,files in ((mobile_root,mobile_files),(tess_root,tess_files)):
            for name,digest in files.items():
                if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:
                    p.exit(1,f'iphoneos artifact changed after build: {name}\n')
    for name in mods:
        for suffix in ('patched.bin','fixups.tsv','gates.tsv'):
            if not (out/f'{name}.{suffix}').is_file():
                p.exit(1, f'Missing rewrite output: {name}.{suffix}\n')
    # Both signed images are required for the launcher's mode selector. Never
    # modify executable pages at runtime or embed only a changed output getter.
    import mobile_graphics_profile as render
    import mobile_camera_profile as camera
    from verify_graphics_profile import verify
    original=(out/'main.patched.bin').read_bytes()
    llvm=Path('/opt/homebrew/opt/llvm/bin/llvm-mc')
    # Verify the actual composed recipe before changing the generated app.
    proof=verify(original,llvm,configurator=lambda data:camera.configure(render.configure(data)),
                 sites=(*render.sites(),*render.SELECTORS))
    camera_proof=camera.verify(render.configure(original),llvm)
    wide_out=render.launch_directory(work,work/'ios-profiles'/str(time.time_ns()))
    configured=camera.configure((wide_out/'main.patched.bin').read_bytes())
    (wide_out/'main.patched.bin').write_bytes(configured)
    graphics=json.loads((wide_out/'graphics.json').read_text())
    graphics.update(mode='mobile-expanded-fov',configured_sha256=hashlib.sha256(configured).hexdigest(),
                    camera_sites=[{'offset':hex(o),'original_word':hex(a),'configured_word':hex(b),'purpose':s}
                                  for o,a,b,s in camera.sites()],
                    verification={'render':proof,'camera':camera_proof},limitations=list(camera.LIMITATIONS),
                    startup_selection=True,normal_image_sha256=receipt['modules']['main']['patched.bin_sha256'])
    assert graphics['configured_sha256']==camera_proof['configured_sha256']
    (wide_out/'graphics.json').write_text(json.dumps(graphics,indent=2)+'\n')
    # The alias changes section names only. Runtime module identity, fixups,
    # HLE gates and original offsets remain main in both modes.
    for suffix in ('patched.bin','fixups.tsv'):
        (wide_out/f'mainwide.{suffix}').symlink_to((wide_out/f'main.{suffix}').resolve())
    if gen.exists():
        gen.rename(ios/('Gen.previous-'+str(time.time_ns())))
    for part in ('dm','msl'):
        (gen/part).mkdir(parents=True,exist_ok=True)
    shutil.copy2(wide_out/'graphics.json',gen/'dm/mobile-graphics.json')
    config = subprocess.check_output([sys.executable,DM/'ios/tools/gen_build.py',DM/'host',gen,
                                      'Makefile.bayonetta3','dmhost_bayonetta3'], text=True)
    flags = subprocess.check_output([sys.executable,DM/'ios/tools/gen_embed.py',out,gen/'embed.S',*mods], text=True).strip()
    flags += ' '+subprocess.check_output([sys.executable,DM/'ios/tools/gen_embed.py',wide_out,wide_out/'embed-wide.S','mainwide'],text=True).strip()
    with (gen/'embed.S').open('a') as f:f.write('\n'+(wide_out/'embed-wide.S').read_text())
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
    assets={}
    for kind,directory,pattern in (('romfs',work/'game/RomFS','*'),('media',work/'media','*.mp4')):
        assets[kind]={path.relative_to(directory).as_posix():path.stat().st_size for path in sorted(directory.rglob(pattern)) if path.is_file()}
    if not assets['romfs'] or not assets['media']:p.exit(1,'Complete private RomFS and prepared native media required\n')
    (gen/'dm/private-assets.json').write_text(json.dumps(assets,indent=2)+'\n')
    if mobile_files:
        target=gen/'msl'/mobile_root.name;target.mkdir()
        for name in mobile_files:shutil.copy2(mobile_root/name,target/name)
        target=gen/'tessellation';target.mkdir()
        for name in tess_files:shutil.copy2(tess_root/name,target/name)
    else:
        (gen/'tessellation').mkdir()
    # Project-owned logo only; generated assets stay under ignored Gen/.
    subprocess.run(['swift',str(ROOT/'tools/build_icon.swift'),str(ROOT)],check=True)
    icons=gen/'Assets.xcassets/AppIcon.appiconset';icons.mkdir(parents=True)
    shutil.copy2(work/'build/icons/AppIcon.png',icons/'AppIcon1024.png')
    (icons/'Contents.json').write_text(json.dumps({'images':[{'filename':'AppIcon1024.png','idiom':'universal','platform':'ios','size':'1024x1024'}],'info':{'author':'xcode','version':1}})+'\n')
    (gen/'Assets.xcassets/Contents.json').write_text('{"info":{"author":"xcode","version":1}}\n')
    env = dict(os.environ, DM_BUNDLE_ID=a.bundle_id, DM_TEAM_ID=a.team_id)
    subprocess.run(['xcodegen','generate','--spec',str(ios/'project.yml')], env=env,check=True,cwd=ios)
    if not a.generate_only:
        log = work/'build-ios.log'
        with log.open('w') as f:
            command=['xcodebuild','-project',str(ios/'Bayonetta3IOS.xcodeproj'),'-scheme','Bayonetta3',
                                    '-configuration',a.configuration,'-destination',('id='+a.device if a.device else 'generic/platform=iOS'),
                                    '-derivedDataPath',str(work/'ios')]
            command+=['-allowProvisioningUpdates','-allowProvisioningDeviceRegistration'] if a.sign else ['CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO']
            result = subprocess.run(command+['build'],stdout=f,stderr=subprocess.STDOUT,env=env)
        if result.returncode:
            p.exit(result.returncode,f'iOS build failed: {log}\n')
        print(f'{"Development-signed" if a.sign else "Unsigned"} iOS host compiled: {work}/ios/Build/Products/{a.configuration}-iphoneos/Bayonetta3.app')
        print('Build only. No device install or on-device gameplay verified.')


if __name__ == '__main__':
    main()
