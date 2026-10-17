#!/usr/bin/env python3
"""Import validated original ROM shader pairs into private offline-build inputs.

Preserves existing captures and records origins separately. Never publishes
game content. Unknown legacy layouts remain visible and are not force accepted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import os
from scan_rom import pkz_directory, dat_leaves, shader_record, DecoderWorker

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,default=ROOT/'work')
    p.add_argument('--decoder-worker',type=Path,required=True)
    a=p.parse_args();w=a.work.resolve()
    profile=json.loads((ROOT/'config/bayonetta3-1.2.0.json').read_text())
    for name,expected in profile['modules'].items():
        data=(w/'game/ExeFS'/name).read_bytes()
        if data[:4]!=b'NSO0' or data[0x40:0x60].hex()!=expected['build_id'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
            raise ValueError('Unrecognized source module '+name)
    path=w/'game/RomFS/root_000.pkz';archive_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    worker=DecoderWorker(a.decoder_worker);pairs={};legacy=[]
    try:
        with path.open('rb') as f:
            for row in pkz_directory(path):
                f.seek(row['offset']);packed=f.read(row['stored'])
                data=packed if row['compression']=='None' else worker.decode(packed,row['size'])
                for r in dat_leaves(data,row['name']):
                    if Path(r['name']).suffix not in ('.vso','.pso','.cso','.hso','.dso','.gso'):continue
                    try:meta,ctl,code=shader_record(memoryview(data)[r['offset']:r['offset']+r['size']])
                    except (ValueError,struct.error) as error:
                        legacy.append({'source':r['name'],'reason':str(error)});continue
                    key=meta['key']
                    if key in pairs and pairs[key][1:]!=(ctl,code):raise ValueError('Conflicting original shader key')
                    sources=pairs[key][0]['sources'] if key in pairs else []
                    sources.append(r['name'])
                    pairs[key]=(dict(meta,source=r['name'],sources=sources),ctl,code)
    finally:worker.close()
    destination=w/'shdump';destination.mkdir(exist_ok=True);added=[]
    # Validate the entire input before publishing any pairs.
    for key,(meta,ctl,code) in pairs.items():
        cp=destination/(key+'.ctl');bp=destination/(key+'.code')
        if cp.exists() or bp.exists():
            if not cp.exists() or not bp.exists() or cp.read_bytes()!=ctl or bp.read_bytes()!=code:
                raise ValueError('Existing capture conflicts with original ROM '+key)
        else:added.append(key)
    with tempfile.TemporaryDirectory(prefix='rom-shaders-',dir=w) as td:
        stage=Path(td)
        for key in added:
            _,ctl,code=pairs[key];(stage/(key+'.ctl')).write_bytes(ctl);(stage/(key+'.code')).write_bytes(code)
        for key in added:
            os.replace(stage/(key+'.code'),destination/(key+'.code'))
            os.replace(stage/(key+'.ctl'),destination/(key+'.ctl'))
    out=w/'shaders/rom_import.json';previous=json.loads(out.read_text()) if out.exists() else {}
    prior=previous.get('imported',[]) if previous.get('archive_sha256')==archive_sha else []
    report={'schema':1,'archive_sha256':archive_sha,'imported':sorted(set(prior+added)),'added_this_run':added,'original_pairs':[m for m,_,_ in pairs.values()],
            'legacy_uninterpreted':legacy,'scope':'Offline original ROM inputs; imported does not mean submitted or gameplay verified'}
    out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Imported {len(added)} additional original pairs; {len(pairs)} known ROM pairs, {len(legacy)} legacy entries left explicit')

if __name__=='__main__':main()
