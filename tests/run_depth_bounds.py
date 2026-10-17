#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'third_party/blade2-mobile/dm/gfx/tools'))
from title_alpha import title_depth_bounds
src='''#include <metal_stdlib>
using namespace metal;
vertex float4 v(uint i [[vertex_id]]) {const float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[i],0.9,1);}
struct main0_out {float4 color [[color(0)]];};
fragment main0_out main0(device atomic_uint* counter [[buffer(1)]]) {
 atomic_fetch_add_explicit(counter,1u,memory_order_relaxed);
 main0_out out={};out.color=float4(1);return out;
}
'''
w=ROOT/'work';(w/'depth_bounds_test.metal').write_text(title_depth_bounds(src))
subprocess.run(['clang','-fobjc-arc','-framework','Metal','-framework','Foundation',str(ROOT/'tests/test_depth_bounds.m'),'-o',str(w/'test-depth-bounds')],check=True)
subprocess.run([str(w/'test-depth-bounds'),str(w/'depth_bounds_test.metal')],check=True)
