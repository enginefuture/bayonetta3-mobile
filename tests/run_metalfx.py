#!/usr/bin/env python3
"""Real GPU tests of spatial scaling and experimental image-motion interpolation."""
from pathlib import Path
import os
import subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work';work.mkdir(exist_ok=True)
for name in ('spatial','motion'):
    binary=work/('test-metalfx-'+name)
    subprocess.run(['clang','-O1','-fobjc-arc','-mmacosx-version-min=26.0',str(ROOT/'tests'/('test_metalfx_'+name+'.m')),'-framework','Metal','-framework','MetalFX','-framework','Foundation','-framework','QuartzCore','-o',str(binary)],check=True)
    subprocess.run([str(binary)],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True)

# Exercise the iOS sizing branch on the host GPU before deploying it.
binary=work/'test-metalfx-ios-size'
subprocess.run(['clang','-O1','-fobjc-arc','-mmacosx-version-min=26.0','-DDM_TEST_IOS_SIZE=1',str(ROOT/'tests/test_metalfx_spatial.m'),'-framework','Metal','-framework','MetalFX','-framework','Foundation','-framework','QuartzCore','-o',str(binary)],check=True)
subprocess.run([str(binary)],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True)
