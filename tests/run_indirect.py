#!/usr/bin/env python3
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'work/test-indirect'
subprocess.run(['clang','-fobjc-arc','-framework','Metal','-framework','Foundation',str(ROOT/'tests/test_indirect.m'),'-o',str(out)],check=True)
subprocess.run([str(out)],check=True)
