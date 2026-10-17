#!/usr/bin/env python3
"""Build observed original VS/TCS/TES into a private, checksummed Metal supplement."""
import argparse
import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from tessellation_shaders import lower,bindings,execution_modes,CONTROL_POINT_BYTES,prepare_tes_subgroups,initialize_tes_subgroup
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'third_party/blade2-mobile/dm/gfx/tools'))
from nvn_capture import capture_stage

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,default=ROOT/'work');a=p.parse_args();w=a.work.resolve()
 chain=re.search(r'DMSH_CHAIN "(\w+)"',(ROOT/'third_party/blade2-mobile/dm/gfx/nvn/dmsh_chain.h').read_text())[1]
 pairs=set()
 for ln in (w/'shaders/pairs.tsv').read_text().splitlines():
  d=dict(x.split(':',1) for x in ln.split() if ':' in x)
  if {'0','3','4'}<=d.keys():pairs.add((d['0'],d['3'],d['4']))
 if not pairs:p.exit(1,'No observed VS/TCS/TES combinations; capture the actual failing program first\n')
 final=w/'build/cache/tessellation'/chain;final.parent.mkdir(parents=True,exist_ok=True)
 dest=Path(tempfile.mkdtemp(prefix='_tess-build-',dir=final.parent));atexit.register(shutil.rmtree,dest,ignore_errors=True)
 temp=w/'tess/build';temp.mkdir(parents=True,exist_ok=True)
 keys={k:s for vs,tc,te in pairs for k,s in ((vs,'vs'),(tc,'tcs'),(te,'tes'))}
 # Inspect/build all already-captured control/evaluation stages, including
 # ones not yet submitted, so the next material need not fail for this omission.
 for record in json.loads((w/'shpack/capture_report.json').read_text())['unsupported']:
  if record['stage'] in ('tcs','tes'):keys[record['key']]=record['stage']
 # Prebuild vertex compute variants from the same named ROM shader families.
 # This is a conservative candidate inventory, not a claim of observed pairs.
 imported=w/'shaders/rom_import.json';family_vertices=[]
 if imported.exists():
  originals=json.loads(imported.read_text())['original_pairs'];families=set()
  for row in originals:
   if row['stage'] in ('tcs','tes'):
    for source in row.get('sources',[row['source']]):
     m=re.match(r'(?:HS|DS)_([^_]+)_',source.rsplit('!',1)[-1])
     if m:families.add(m[1])
  for row in originals:
   if row['stage']=='vs':
    for source in row.get('sources',[row['source']]):
     m=re.match(r'VS_([^_]+)_',source.rsplit('!',1)[-1])
     if m and m[1] in families:
      keys[row['key']]='vs';family_vertices.append(row['key']);break
 facts={ln.split('\t',1)[0]:json.loads(ln.split('\t',1)[1]) for ln in (w/'shaders/shader_facts.tsv').read_text().splitlines() if '\t' in ln and not ln.startswith('#')}
 jobs=[];c1s={};inputs={}
 for key,stage in sorted(keys.items()):
  ctl=(w/'shdump'/(key+'.ctl')).read_bytes();code=(w/'shdump'/(key+'.code')).read_bytes()
  if capture_stage(key,ctl,code)!=stage:raise ValueError('Capture stage mismatch')
  if stage=='tes' and (len(ctl)!=0x880 or struct.unpack_from('<3I',ctl,0x868)!=(1,0,0)):
   raise ValueError('Unverified TES state metadata: only the captured triangle/equal/CCW contract is implemented')
  c1o,c1n=struct.unpack_from('<2I',ctl,0x700);c1s[key]=code[c1o:c1n].hex();cp=temp/(key+'.bin');cp.write_bytes(code[0x30:])
  j={'key':key,'stage':stage,'code':str(cp),'c1':c1s[key],'debug':True,'reduced':True,**facts.get(key,{})}
  jobs.append(j);inputs[key]={'control_sha256':hashlib.sha256(ctl).hexdigest(),'code_sha256':hashlib.sha256(code).hexdigest()}
 jp=temp/'jobs.json';jp.write_text(json.dumps(jobs));env=dict(os.environ,DOTNET_ROOT=str(w/'toolchains/dotnet'))
 subprocess.run([str(w/'build/gfx/dmsh_xlate/dmsh_xlate'),str(jp),str(temp)],env=env,check=True)
 cross=w/'toolchains/bin/spirv-cross'
 tool_files=[cross,w/'build/gfx/dmsh_xlate/dmsh_xlate',*sorted((w/'build/gfx/dmsh_xlate').glob('*.dll'))]
 toolchain={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in tool_files}
 toolchain['metal_version']=subprocess.check_output(['xcrun','-sdk','macosx','metal','--version'],text=True).strip()
 def build(item):
  key,stage=item;spv=temp/(key+'.spv');rfile=temp/(key+'.cross.json');msl=temp/(key+'.metal')
  subgroup=False
  if stage=='tes':
   prepared,subgroup=prepare_tes_subgroups(spv.read_bytes())
   if subgroup:spv=temp/(key+'.lane.spv');spv.write_bytes(prepared)
  subprocess.run([str(cross),str(spv),'--reflect','--output',str(rfile)],check=True)
  opts={'vs':['--msl-vertex-for-tessellation'],'tcs':['--msl-multi-patch-workgroup'],'tes':['--msl-raw-buffer-tese-input']}[stage]
  subprocess.run([str(cross),str(spv),'--msl','--msl-version','20300','--msl-argument-buffers','--msl-texture-buffer-native',*opts,'--output',str(msl)],check=True,capture_output=True,text=True)
  modes=execution_modes(spv.read_bytes())
  if stage=='tcs' and modes.get(26)!=[3]:raise ValueError('Unverified TCS output patch size')
  source=msl.read_text()
  if subgroup:source=initialize_tes_subgroup(source)
  source=lower(source,json.loads(rfile.read_text()),stage)
  suffix={'vs':'tv','tcs':'tc','tes':'te'}[stage];name=key+'_'+suffix;output=dest/(name+'.metal');output.write_text(source)
  air=temp/(name+'.air');lib=dest/(name+'.metallib')
  subprocess.run(['xcrun','-sdk','macosx','metal','-c','-fpreserve-invariance',str(output),'-o',str(air)],check=True)
  subprocess.run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(lib)],check=True)
  res=json.loads((temp/(key+'.res.json')).read_text())
  meta={'key':name,'stage':{'vs':'tess-vs','tcs':'tcs','tes':'tes'}[stage],'route':'B','chain':chain,'entry':'main0','c1':c1s[key],'notes':res['notes'],'bindings':bindings(source),'drv_reads':{},'drv_unfillable':[],
        'vertex_inputs':[{'location':int(l),'msl_type':ty} for ty,l in re.findall(r'\b(\w+)\s+\w+\s*\[\[attribute\((\d+)\)\]\]',source)],'control_point_bytes':CONTROL_POINT_BYTES,'output_points':3,'tessellation_domain':'triangle','execution_modes':modes,'physical_subgroup_lane':subgroup}
  (dest/(name+'.json')).write_text(json.dumps(meta,indent=2)+'\n');return name
 names=[];failures={}
 def attempt(item):
  try:return build(item),None
  except (ValueError,subprocess.CalledProcessError) as error:return item[0],(error.stderr or str(error)).strip() if isinstance(error,subprocess.CalledProcessError) else str(error)
 with ThreadPoolExecutor(max_workers=6) as executor:
  for name,error in executor.map(attempt,sorted(keys.items())):
   if error:failures[name]=error
   else:names.append(name)
 required={k:s for vs,tc,te in pairs for k,s in ((vs,'vs'),(tc,'tcs'),(te,'tes'))}
 if any(k in failures for k in required):raise ValueError('An observed tessellation stage is unsupported: '+str({k:failures[k] for k in required if k in failures}))
 expected={name+suffix for name in names for suffix in ('.metal','.metallib','.json')}
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for name in names for p in (dest/(name+'.metal'),dest/(name+'.metallib'),dest/(name+'.json'))}
 receipt={'unsupported':failures,'schema':1,'chain':chain,'pairs':[list(x) for x in sorted(pairs)],'family_vertex_candidates':sorted(family_vertices),'inputs':inputs,'files':files,'toolchain':toolchain,'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'lowering_sha256':hashlib.sha256((ROOT/'tools/tessellation_shaders.py').read_bytes()).hexdigest()}
 (dest/'_tessellation.json').write_text(json.dumps(receipt,indent=2)+'\n')
 # An unsupported required stage or compiler failure leaves the previous cache
 # intact. Install complete files atomically and publish the new receipt last.
 final.mkdir(parents=True,exist_ok=True)
 for name in sorted(files):os.replace(dest/name,final/name)
 for old in final.iterdir():
  if old.is_file() and re.fullmatch(r'[0-9a-f]{16}_(?:tv|tc|te)\.(?:metal|metallib|json)',old.name) and old.name not in expected:old.unlink()
 os.replace(dest/'_tessellation.json',final/'_tessellation.json')
 print('Unimplemented captured stages:',','.join(failures) or 'none');print(f'Tessellation supplement: {len(names)} stages / {len(pairs)} observed combinations: {final}')
if __name__=='__main__':main()
