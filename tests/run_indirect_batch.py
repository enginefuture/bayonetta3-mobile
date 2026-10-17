#!/usr/bin/env python3
"""Exercise production replay planning and GPU count preparation, without game inputs."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
gfx=ROOT/'third_party/blade2-mobile/dm/gfx'
objects=[]
for directory in ('nvn','tex'):
    for source in sorted((gfx/directory).iterdir()):
        if source.suffix in ('.c','.m') and source.name not in ('hle_nvn.c','nvn_mtl.m'):
            objects.append(str(source))
cmd=['clang','-O1','-g','-Wall','-Wno-unused-function','-DDM_BAYONETTA3=1','-DDM_GENERIC_HOST=1',
     '-mmacosx-version-min=26.0','-fobjc-arc','-I'+str(gfx/'nvn/include'),
     str(ROOT/'tests/test_indirect_batch.m'),str(ROOT/'third_party/blade2-mobile/dm/host/crash.c'),*objects,
     '-o',str(ROOT/'work/test-indirect-batch')]
for framework in ('Metal','Foundation','QuartzCore','ImageIO','CoreGraphics','UniformTypeIdentifiers'):
    cmd+=['-framework',framework]
subprocess.run(cmd,check=True)
subprocess.run([str(ROOT/'work/test-indirect-batch')],check=True)
