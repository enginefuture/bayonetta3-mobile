#!/usr/bin/env python3
"""Validate original production upload against independently placed ASTC blocks."""
from pathlib import Path
import os
import subprocess
ROOT=Path(__file__).resolve().parents[1]
gfx=ROOT/'third_party/blade2-mobile/dm/gfx'
sources=[str(p) for d in ('nvn','tex') for p in sorted((gfx/d).iterdir()) if p.suffix in ('.c','.m') and p.name not in ('hle_nvn.c','nvn_mtl.m')]
cmd=['clang','-O1','-g','-Wall','-Wno-unused-function','-DDM_BAYONETTA3=1','-DDM_GENERIC_HOST=1','-mmacosx-version-min=26.0','-fobjc-arc','-I'+str(gfx/'nvn/include'),str(ROOT/'tests/test_texture_layout.m'),str(ROOT/'third_party/blade2-mobile/dm/host/crash.c'),*sources,'-o',str(ROOT/'work/test-texture-layout')]
for framework in ('Metal','MetalFX','Foundation','QuartzCore','ImageIO','CoreGraphics','UniformTypeIdentifiers'):cmd+=['-framework',framework]
subprocess.run(cmd,check=True)
subprocess.run([str(ROOT/'work/test-texture-layout')],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True)
