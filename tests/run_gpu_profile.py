#!/usr/bin/env python3
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
w=ROOT/'work';w.mkdir(exist_ok=True)
subprocess.run(['clang','-fobjc-arc','-mmacosx-version-min=26.0','-framework','Metal','-framework','Foundation',str(ROOT/'tests/test_gpu_profile.m'),str(ROOT/'third_party/blade2-mobile/dm/gfx/nvn/nvn_gpu_profile.m'),'-o',str(w/'test-gpu-profile')],check=True)
subprocess.run([str(w/'test-gpu-profile'),str(w/'test-gpu-profile.tsv')],check=True)
