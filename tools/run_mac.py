#!/usr/bin/env python3
"""Launch the native host with isolated saves; optionally show Apple's Metal HUD."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import time
from media_cache import movie_inventory
from shader_interfaces import verify_receipt
from run_diagnostics import execute, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,default=ROOT/'work')
    p.add_argument('--seconds',type=int,default=30,help='Diagnostic time limit, 1..600 seconds; 0 leaves the game open until closed')
    p.add_argument('--metal-hud',action='store_true',help='Show Apple Metal Performance HUD for this process')
    p.add_argument('--metal-hud-log',action='store_true',help='Enable Metal HUD and its performance logging for this process')
    p.add_argument('--profile',action='store_true',help='Record bounded per-frame CPU/GPU, upload and pass metrics privately')
    p.add_argument('--gpu-profile',action='store_true',help='Diagnostic Metal4 per-encoder timestamps; changes timing, not an FPS benchmark')
    p.add_argument('--gpu-profile-every',type=int,default=60,choices=range(1,3601),metavar='1..3600')
    p.add_argument('--indirect-batch',type=int,choices=(0,1),default=1,help='Batch GPU indirect-count preparation across proven read-only commands')
    p.add_argument('--indirect-batch-control',type=Path,help='Local diagnostic A/B policy file: 0 or 1, polled every 60 frames')
    p.add_argument('--profile-log-mib',type=int,default=32,choices=range(1,257),metavar='1..256')
    p.add_argument('--skip-media-preflight',action='store_true',help='Diagnostic only: allow incomplete movie caches; chapter progression can abort')
    p.add_argument('--trace-fs',action='store_true',help='Log local file opens and read counters')
    p.add_argument('--trace-nvn',action='store_true',help='Log NVN object creation and queried capabilities')
    p.add_argument('--hid-receipt',action='store_true',help='Record actual Npad state returned to the game in an isolated JSONL receipt')
    p.add_argument('--capture-shaders',action='store_true',help='Diagnostic mode: allow missing shader libraries; resulting frames are incomplete')
    p.add_argument('--debug-script',type=Path,help='LLDB batch commands for local startup diagnosis')
    p.add_argument('--shot',help='Capture actual present frames: frame[,frame]:absolute-path-with-percent-d')
    p.add_argument('--input-script',type=Path,help='Post timed native NSEvent input from a local script (seconds key mac-keycode)')
    p.add_argument('--pad-sequence',help='Diagnostic timed Npad buttons, e.g. A@7+0.3,A@10+0.3; ORed with physical input')
    p.add_argument('--present-link',type=int,choices=(0,1,2),default=0,help='0: direct drawable pacing; 1/2: display-link pacing')
    p.add_argument('--inspect-frame',type=int,help='Dump one actual guest frame: render targets, draw/resource bindings and uniform bytes')
    p.add_argument('--probe-depth-keys',help='Diagnostic only: disable depth comparison for listed fragment keys; resulting frames cannot pass validation')
    a = p.parse_args()
    if not 0 <= a.seconds <= 600:
        p.error('--seconds must be 0..600 (0 leaves the game open)')
    w = a.work.resolve()
    receipt = json.loads((w/'verification.json').read_text())
    profile = json.loads((ROOT/'config/bayonetta3-1.2.0.json').read_text())
    if not receipt.get('passed') or set(receipt['modules']) != set(profile['runtime_modules']):
        p.exit(1,'Complete structural/equivalence verification required\n')
    for name in profile['runtime_modules']:
        for suffix in ('patched.bin','fixups.tsv','gates.tsv','sites.tsv','cuts.tsv'):
            digest = hashlib.sha256((w/'rewrite'/f'{name}.{suffix}').read_bytes()).hexdigest()
            if digest != receipt['modules'][name][suffix+'_sha256']:
                p.exit(1,f'{name}: rewrite changed after verification\n')
    romfs = w/'game/RomFS'
    if not (romfs/profile['romfs_marker']).is_file():
        p.exit(1,'Missing Bayonetta 3 RomFS\n')
    for part in ('run/save','run/temp','run/log','shaders','shdump'):
        (w/part).mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())
    log=w/'run/log'/('native-'+stamp+'.log')
    if not a.skip_media_preflight:
        print('Checking original movie/cache hashes before chapter play...',flush=True)
        movies=movie_inventory(romfs/'movie',w/'media')
        missing=[m for m in movies if not m['ready']]
        write_json(log.with_suffix('.preflight.json'),{'movies':movies,'ready':bool(movies) and not missing})
        if missing or not movies:
            names=', '.join(Path(m['source']).name for m in missing[:12])
            p.exit(2,f'Movie preflight failed: {len(missing)}/{len(movies)} caches missing/invalid ({names}).\n'
                     'Prepare the complete directory before launching:\n'
                     f'  .venv/bin/python tools/prepare_media.py "{romfs}/movie" --cache "{w}/media"\n')
        print(f'{len(movies)} original movie caches verified.',flush=True)
    else:print('Diagnostic: movie preflight skipped; no full chapter pass.',flush=True)
    if not a.capture_shaders:
        header=(ROOT/'third_party/blade2-mobile/dm/gfx/nvn/dmsh_chain.h').read_text()
        chain=re.search(r'#define DMSH_CHAIN "([0-9a-f]{12})"',header).group(1)
        try:
            interfaces=verify_receipt(w/'build/cache/metal_shader_cache'/('b-'+chain),chain)
        except (OSError,ValueError,KeyError) as error:
            p.exit(2,f'Shader interface preflight failed: {error}\nRebuild the complete cache with tools/build_shaders.py and rebuild the host.\n')
        print(f"Shader varying ABI verified: {interfaces['vertices']} vertex / {interfaces['fragments']} fragment libraries.",flush=True)
    shmap = w/'shaders/shader_map.tsv'
    if not shmap.exists():
        shmap.write_text('# Bayonetta 3 shader capture pending\n')
    env = {k:v for k,v in os.environ.items() if not k.startswith('DM_')}
    env.update(DM_ROOT=str(w),DM_ROMFS=str(romfs),DM_SAVE=str(w/'run/save'),DM_TEMP=str(w/'run/temp'),
               DM_NVN_SHMAP=str(shmap),DM_NVN_USED_SHADERS=str(w/'shaders/used.txt'),DM_NVN_SHDUMP=str(w/'shdump'),DM_NVN_PAIRS=str(w/'shaders/pairs.tsv'),
               DM_NVN_TEXFACTS=str(w/'shaders/texfacts.tsv'),DM_PSO_MANIFEST='off',DM_NVN_TBDR='0',DM_SYSRES_MB='0',
               DM_AUDIO='1',DM_MOVIE='1',DM_MOVIE_CACHE=str(w/'media'),DM_WINDOW='1',DM_WATCH=str(a.seconds),DM_DBG='1',DM_LOADHASH='1',DM_PRESENT_LINK=str(a.present_link))
    if not a.seconds:env.pop('DM_WATCH',None)
    if a.metal_hud or a.metal_hud_log:env['MTL_HUD_ENABLED']='1'
    if a.metal_hud_log:env['MTL_HUD_LOG_ENABLED']='1'
    if a.profile:
        env.update(DM_NVN_TSV=str(log.with_suffix('.frames.tsv')),DM_NVN_TSV_CALLS='0',
                   DM_NVN_TSV_MAX_MB=str(a.profile_log_mib),DM_SLOWFRAME='1')
    if a.gpu_profile:
        env.update(DM_GPU_PASS_PROFILE=str(log.with_suffix('.passes.tsv')),DM_GPU_PASS_EVERY=str(a.gpu_profile_every))
    env['DM_NVN_INDIRECT_BATCH']=str(a.indirect_batch)
    if a.indirect_batch_control:env['DM_NVN_INDIRECT_BATCH_CONTROL']=str(a.indirect_batch_control.resolve())
    if a.trace_fs:
        env['DM_FS']='1'
    if a.trace_nvn:
        env['DM_NVN_LOG']='1'
    if a.capture_shaders:
        env['DM_NVN_CAPTURE']='1'
        print('Shader capture mode: missing shaders may omit draws; no visual/gameplay pass.',flush=True)
    if a.shot:env['DM_NVN_SHOT']=a.shot
    if a.probe_depth_keys:
        if not re.fullmatch(r'[0-9a-f]{16}(,[0-9a-f]{16}){0,5}',a.probe_depth_keys):p.error('probe keys must be 1..6 comma-separated 16-digit hashes')
        env['DM_NVN_DT_ALWAYS']=a.probe_depth_keys
        print('Depth comparison probe: selected draws modified; no visual/gameplay pass.',flush=True)
    if a.input_script:
        if not a.input_script.is_file():p.error('--input-script must name an existing file')
        env['DM_TEST_NSMOUSE']=str(a.input_script.resolve())
    if a.pad_sequence:
        if len(a.pad_sequence)>4095 or not re.fullmatch(r'[A-Z][A-Z0-9]*@\d+(?:\.\d+)?(?:\+\d+(?:\.\d+)?)?(?:,[A-Z][A-Z0-9]*@\d+(?:\.\d+)?(?:\+\d+(?:\.\d+)?)?)*',a.pad_sequence):p.error('--pad-sequence requires timed button presses')
        env['DM_KEYS']=a.pad_sequence
    if a.inspect_frame is not None:
        if a.inspect_frame<1:p.error('--inspect-frame must be positive')
        diagnostic=w/'run'/f'inspect-{a.inspect_frame}';diagnostic.mkdir(exist_ok=True)
        env.update(DM_NVN_PASSDUMP=str(a.inspect_frame),DM_NVN_PASSDUMP_ALL='1',
                   DM_NVN_TEXDUMP=f'{a.inspect_frame}:{diagnostic}/tex-%d.png',DM_NVN_CBDUMP=str(diagnostic))
    if a.hid_receipt:env['DM_HID_RECEIPT_LOG']=str(log.with_suffix('.hid.jsonl'))
    binary = ROOT/'third_party/blade2-mobile/dm/host/dmhost_bayonetta3'
    print(f'Native experiment; log: {log}',flush=True)
    if a.metal_hud or a.metal_hud_log:print('Metal Performance HUD enabled for this process',flush=True)
    if not a.seconds:print('Interactive run: no watchdog; close the game window or press Command-Q to exit',flush=True)
    cmd=[str(binary),str(w/'rewrite'),*profile['runtime_modules']]
    if a.debug_script:cmd=['xcrun','lldb','--batch','-s',str(a.debug_script.resolve()),'--',*cmd]
    rc=execute(cmd,env,log,{'profile':str(ROOT/'config/bayonetta3-1.2.0.json'),
        'host_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'shader_chain_header':(ROOT/'third_party/blade2-mobile/dm/gfx/nvn/dmsh_chain.h').read_text().strip(),
        'diagnostics':{'profile':a.profile,'gpu_profile':a.gpu_profile,'movie_preflight':not a.skip_media_preflight,
                       'capture_shaders':a.capture_shaders,'shader_interface_preflight':not a.capture_shaders,'present_link':a.present_link,
                       'indirect_batch':a.indirect_batch,'indirect_batch_control':str(a.indirect_batch_control.resolve()) if a.indirect_batch_control else None,
                       'pad_sequence':a.pad_sequence}},
        timeout=a.seconds+15 if a.seconds else None,watchdog=bool(a.seconds))
    raise SystemExit(rc if rc >= 0 else 128-rc)


if __name__ == '__main__':
    main()
