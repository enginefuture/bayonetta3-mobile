#!/usr/bin/env python3
"""Read-only private ROM inventory; resource presence is not gameplay coverage.

PKZ/DAT directory layouts cross-checked against Kerilk/bayonetta_tools
(lib/bayonetta/{pkz,dat}.rb). No assets are extracted or distributed.
An optional isolated local Kraken decoder worker is never loaded by the game.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import subprocess
import atexit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'third_party/blade2-mobile/dm/gfx/tools'))
from nvn_capture import LAYOUTS, capture_stage


def extent(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('Directory extent outside input')
    return memoryview(data)[offset:offset+size]


def cstring(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('String offset outside table')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('Unterminated string')
    return data[offset:end].decode('utf-8')


def pkz_directory(path):
    size = path.stat().st_size
    with path.open('rb') as f:
        header = f.read(32)
        magic, version, declared, count, table, strings, alignment = struct.unpack('<4sIQ4I', header)
        if magic != b'pkzl' or version != 0x20000 or declared != size:
            raise ValueError('Unknown PKZ identity/size/version')
        if count > 1000000 or strings > 64*1024*1024 or table < 32 or table+count*32+strings > size:
            raise ValueError('Invalid PKZ directory')
        f.seek(table)
        entries, names = f.read(count*32), f.read(strings)
    rows = []
    for i in range(count):
        no, co, raw_size, offset, stored = struct.unpack_from('<IIQQQ', entries, i*32)
        name, compression = cstring(names, no), cstring(names, co)
        if name.startswith('/') or '..' in PurePosixPath(name).parts or '\\' in name:
            raise ValueError('Unsafe member name')
        if offset < table+count*32+strings or offset+stored > size or raw_size > 512*1024*1024:
            raise ValueError('Invalid/oversized PKZ member extent')
        if compression == 'None' and stored != raw_size:
            raise ValueError('Uncompressed size mismatch')
        rows.append(dict(name=name, compression=compression, size=raw_size, offset=offset, stored=stored))
    spans = sorted((r['offset'], r['offset']+r['stored']) for r in rows if r['stored'])
    if any(a[1] > b[0] for a,b in zip(spans,spans[1:])):
        raise ValueError('Overlapping PKZ members')
    return rows


def dat_leaves(data, prefix, base=0, depth=0):
    if depth > 12:
        raise ValueError('Nested DAT depth exceeds budget')
    if data[:4] != b'DAT\0':
        yield dict(name=prefix, offset=base, size=len(data), magic=bytes(data[:16]).hex())
        return
    _, count, offsets, extensions, names, sizes, hashes = struct.unpack_from('<4s6I',data)
    if count > 1000000:
        raise ValueError('Oversized DAT directory')
    extent(data, offsets, count*4); extent(data, extensions, count*4); extent(data,sizes,count*4)
    name_length = struct.unpack_from('<I',extent(data,names,4))[0]
    if not 1 <= name_length <= 4096:
        raise ValueError('Invalid DAT name width')
    extent(data,names+4,count*name_length)
    for i in range(count):
        off=struct.unpack_from('<I',data,offsets+i*4)[0]
        size=struct.unpack_from('<I',data,sizes+i*4)[0]
        name=bytes(extent(data,names+4+i*name_length,name_length)).split(b'\0')[0].decode('utf-8')
        view=extent(data,off,size)
        yield from dat_leaves(view,prefix+'!'+name,base+off,depth+1)


def controls(data):
    pos=0
    while True:
        pos=data.find(bytes.fromhex('34127698'),pos)
        if pos<0:return
        current=pos;pos+=4
        if current+0x24>len(data):continue
        _,major,minor=struct.unpack_from('<3I',data,current)
        size=struct.unpack_from('<I',data,current+0x20)[0]
        if major != 1 or LAYOUTS.get(minor)!=size or current+size>len(data):continue
        ctl=data[current:current+size]
        yield dict(offset=current,bytes=size,key=hashlib.sha256(ctl).hexdigest()[:16],minor=minor,
                   c1_offset=struct.unpack_from('<I',ctl,0x700)[0],
                   code_bytes=struct.unpack_from('<I',ctl,0x704)[0])


def shader_record(data):
    magic, version, control_size, control_offset, code_size, code_offset = struct.unpack_from('<6I', data)
    control=bytes(extent(data,control_offset,control_size));code=bytes(extent(data,code_offset,code_size))
    key=hashlib.sha256(control).hexdigest()[:16]
    stage=capture_stage(key,control,code)
    return dict(key=key,stage=stage,minor=struct.unpack_from('<I',control,8)[0],
                control_bytes=control_size,code_bytes=code_size,code_sha256=hashlib.sha256(code).hexdigest()),control,code


def texture_records(data):
    if data[:4] != b'WTB\0':raise ValueError('Unknown WTA/WTB magic')
    _, version, count, offsets, sizes, flags, ids, infos=struct.unpack_from('<8I',data)
    extent(data,offsets,count*4);extent(data,sizes,count*4)
    if not count:return []
    if not infos or data[infos:infos+4]!=b'XT1\0':raise ValueError('Texture information is not XT1')
    extent(data,infos,count*56)
    result=[]
    for i in range(count):
        header=bytes(extent(data,infos+i*56,56))
        magic,version,byte_size,unknown,header_size,levels,target,fmt,width,height,depth,reserved,layout0,layout1=struct.unpack('<4s13I',header)
        if magic!=b'XT1\0' or header_size!=56:raise ValueError('Unknown XT1 header')
        result.append(dict(index=i,format=fmt,target=target,width=width,height=height,depth=depth,
                           levels=levels,layout=header[48:56].hex(),bytes=byte_size,
                           storage_bytes=struct.unpack_from('<I',data,sizes+i*4)[0]))
    return result


class DecoderWorker:
    """Keep third-party decoder faults outside the inventory process."""
    def __init__(self,path):
        self.path=path;self.process=None;atexit.register(self.close)
    def close(self):
        if self.process:
            try:self.process.stdin.close()
            except BrokenPipeError:pass
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process.stdout.close();self.process=None
    def decode(self,packed,size):
        if self.process is None:self.process=subprocess.Popen([str(self.path.resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        try:
            self.process.stdin.write(struct.pack('<QQ',len(packed),size));self.process.stdin.write(packed);self.process.stdin.flush()
            header=self.process.stdout.read(8)
            if len(header)!=8:raise ValueError('External decoder terminated unexpectedly')
            got=struct.unpack('<q',header)[0]
            if got!=size:raise ValueError('Kraken decoded size mismatch: '+str(got))
            data=self.process.stdout.read(size)
            if len(data)!=size:raise ValueError('Truncated external decoder result')
            return data
        except (BrokenPipeError,ValueError) as error:
            self.close();raise ValueError('External decoder failure; resource unverified: '+str(error)) from error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,default=ROOT/'work')
    parser.add_argument('--decoder-worker',type=Path,help='Isolated decoder speaking <QQ sizes / q result / bytes protocol')
    parser.add_argument('--deep',action='store_true',help='Decompress all PKZ members in bounded RAM and inventory DAT leaves')
    a=parser.parse_args();work=a.work.resolve();out=work/'analysis/rom-scan';out.mkdir(parents=True,exist_ok=True)
    worker=DecoderWorker(a.decoder_worker) if a.decoder_worker else None
    captures={p.stem for p in (work/'shdump').glob('*.ctl')}
    report={'schema':1,'scope':'Merged local RomFS; static metadata, not gameplay coverage','deep':a.deep,
            'scanner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'decoder_sha256':hashlib.sha256(a.decoder_worker.read_bytes()).hexdigest() if a.decoder_worker else None,
            'archives':[],'errors':[],'resources':[],'controls':[],'shaders':{},'textures':[],
            'shader_warnings':[],'texture_warnings':[]}
    extensions=Counter();magics=Counter();done=0
    for p in sorted((work/'game/RomFS').glob('*.pkz')):
        rows=pkz_directory(p);digest=hashlib.sha256()
        with p.open('rb') as f:
            while chunk:=f.read(8*1024*1024):digest.update(chunk)
        report['archives'].append({'name':p.name,'bytes':p.stat().st_size,'sha256':digest.hexdigest(),'members':rows})
        if a.deep:
            with p.open('rb') as f:
                for row in rows:
                    label=p.name+'!'+row['name'];done+=1
                    try:
                        (out/'current-member.json').write_text(json.dumps({'source':label}))
                        f.seek(row['offset']);packed=f.read(row['stored'])
                        if row['compression']=='None':data=packed
                        elif row['compression']=='OodleKraken' and worker:data=worker.decode(packed,row['size'])
                        else:raise ValueError('Decoder unavailable for '+row['compression'])
                        leaves=list(dat_leaves(data,label))
                        for r in leaves:
                            extensions[PurePosixPath(r['name']).suffix.lower()]+=1;magics[r['magic'][:8]]+=1
                        report['resources'].extend(leaves)
                        for ctl in controls(data):
                            ctl['source']=label;ctl['captured']=ctl['key'] in captures
                            ctl['resource']=next((r['name'] for r in leaves if r['offset']<=ctl['offset']<r['offset']+r['size']),None)
                            report['controls'].append(ctl)
                        # Retain only small headers, never texture/shader payloads.
                        for r in leaves:
                            suffix=PurePosixPath(r['name']).suffix.lower()
                            if suffix in ('.vso','.pso','.cso','.hso','.dso','.gso'):
                                try:
                                    shader,ctl,code=shader_record(extent(data,r['offset'],r['size']))
                                    key=shader['key'];shader['captured']=key in captures
                                    if shader['captured'] and ((work/'shdump'/(key+'.ctl')).read_bytes()!=ctl or (work/'shdump'/(key+'.code')).read_bytes()!=code):
                                        raise ValueError('Runtime capture byte mismatch')
                                    if key not in report['shaders']:report['shaders'][key]=dict(shader,sources=[])
                                    report['shaders'][key]['sources'].append(r['name'])
                                except (ValueError,struct.error) as error:
                                    report['shader_warnings'].append({'source':r['name'],'reason':str(error),'header':data[r['offset']:r['offset']+min(r['size'],64)].hex()})
                            if PurePosixPath(r['name']).suffix.lower() in ('.wta','.wtb'):
                                r['header']=data[r['offset']:r['offset']+min(64,r['size'])].hex()
                                try:
                                    for texture in texture_records(extent(data,r['offset'],r['size'])):
                                        report['textures'].append(dict(texture,source=r['name']))
                                except (ValueError,struct.error) as error:
                                    report['texture_warnings'].append({'source':r['name'],'reason':str(error)})
                    except (ValueError,struct.error,UnicodeError) as e:
                        report['errors'].append({'source':label,'reason':str(e)})
            print(f"{p.name}: {len(rows)} members; leaves={len(report['resources'])}; controls={len(report['controls'])}; errors={len(report['errors'])}",flush=True)
        else:print(f'{p.name}: {len(rows)} members',flush=True)
        # Progress checkpoint is private and permits inspecting partial coverage.
        (out/'partial.json').write_text(json.dumps(report))
        (out/'progress.json').write_text(json.dumps({'last_archive':p.name,'members':done,'errors':len(report['errors'])}))
    files=list((work/'game/RomFS').rglob('*'))
    report['summary']={'romfs_files':sum(p.is_file() for p in files),'archives':len(report['archives']),
      'archive_bytes':sum(r['bytes'] for r in report['archives']),
      'members':sum(len(r['members']) for r in report['archives']),
      'decoded_members':done-len(report['errors']) if a.deep else 0,
      'expanded_bytes':sum(m['size'] for r in report['archives'] for m in r['members']),
      'resource_extensions':dict(extensions),'resource_magic4':dict(magics),
      'control_occurrences':len(report['controls']),'control_unique':len({r['key'] for r in report['controls']}),
      'uncaptured_control_unique':len({r['key'] for r in report['controls'] if not r['captured']})}
    report['summary'].update(shader_stage_unique=dict(Counter(s['stage'] for s in report['shaders'].values())),
        uncaptured_shader_stages=dict(Counter(s['stage'] for s in report['shaders'].values() if not s['captured'])),
        shader_warnings=len(report['shader_warnings']),texture_warnings=len(report['texture_warnings']),
        textures=len(report['textures']),texture_formats=dict(Counter(t['format'] for t in report['textures'])),
        texture_targets=dict(Counter(t['target'] for t in report['textures'])),
        texture_layouts=dict(Counter(t['layout'] for t in report['textures'])))
    target=out/'inventory.json';target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2));print('Private report:',target)
    if report['errors']:raise SystemExit(1)

if __name__=='__main__':main()
