#!/usr/bin/env python3
"""Resume private RomFS/movie transfers to an explicitly selected physical device.

Skip files whose lengths already match, copy one file at a time, and verify the
remote inventory afterwards. Does not copy saves or publish any game content.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device',required=True)
    p.add_argument('--bundle-id',required=True)
    p.add_argument('--kind',choices=('romfs','media','all'),default='all')
    p.add_argument('--work',type=Path,default=ROOT/'work')
    a=p.parse_args();w=a.work.resolve();logs=w/'ios-device';logs.mkdir(parents=True,exist_ok=True)
    common=['--device',a.device,'--domain-type','appDataContainer','--domain-identifier',a.bundle_id]
    roots={'romfs':(w/'game/RomFS','Library/Application Support/romfs'),'media':(w/'media','Documents/media')}
    def inventory(kind,dest):
        receipt=logs/(kind+'-remote-files.json')
        command=['xcrun','devicectl','device','info','files',*common,'--subdirectory',dest,'--json-output',str(receipt)]
        with (logs/(kind+'-remote-files.log')).open('w') as f:
            r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
        if r.returncode:
            # A brand-new media folder is allowed; all other failures stay visible.
            error=(logs/(kind+'-remote-files.log')).read_text()
            if 'does not exist' in error or 'Failed to retrieve the file node' in error:return {}
            raise RuntimeError('Cannot inspect device inventory: '+error[-900:])
        result=json.loads(receipt.read_text())['result']
        return {row['relativePath']:row['metadata']['size'] for row in result['files'] if not row['resources']['isDirectory']}
    journal=[]
    for kind in (roots if a.kind=='all' else (a.kind,)):
        src,dest=roots[kind]
        # Only AVC files are consumed by the device; keep source conversion
        # receipts on the Mac rather than starting hundreds of tiny transfers.
        files={f.relative_to(src).as_posix():f for f in sorted(src.rglob('*.mp4' if kind=='media' else '*')) if f.is_file()}
        if not files:raise ValueError('Empty local asset directory: '+str(src))
        remote=inventory(kind,dest)
        todo=[(name,f) for name,f in files.items() if remote.get(name)!=f.stat().st_size]
        completed=len(files)-len(todo);total=sum(f.stat().st_size for _,f in todo);sent=0
        print(f'{kind}: {completed}/{len(files)} complete; {total/1e9:.3f} GB to transfer',flush=True)
        for name,f in todo:
            started=time.monotonic()
            command=['xcrun','devicectl','device','copy','to',*common,'--source',str(f),'--destination',dest+'/'+name]
            for attempt in range(3):
                with (logs/'transfer-current.log').open('w') as out:
                    r=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
                if r.returncode==0:break
                print(f'{kind}/{name}: transfer failed, attempt {attempt+1}/3; see transfer-current.log',flush=True)
            if r.returncode:raise RuntimeError('Device transfer failed after three attempts: '+name)
            sent+=f.stat().st_size;completed+=1
            journal.append({'kind':kind,'path':name,'size':f.stat().st_size,'seconds':round(time.monotonic()-started,3)})
            (logs/'transfer-journal.json').write_text(json.dumps(journal,indent=2)+'\n')
            print(f'{kind}: {completed}/{len(files)}; {sent/1e9:.3f}/{total/1e9:.3f} GB newly sent; {name}',flush=True)
        remote=inventory(kind,dest)
        bad=[name for name,f in files.items() if remote.get(name)!=f.stat().st_size]
        if bad:raise RuntimeError(f'{kind}: {len(bad)} mismatched files after transfer: {bad[:5]}')
        (logs/(kind+'-transfer-verified.json')).write_text(json.dumps({'kind':kind,'files':len(files),'bytes':sum(f.stat().st_size for f in files.values()),'verification':'Remote file lengths; not a content-hash proof'},indent=2)+'\n')
        print(f'{kind}: all {len(files)} remote file lengths verified',flush=True)

if __name__=='__main__':main()
