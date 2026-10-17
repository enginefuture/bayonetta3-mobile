#!/usr/bin/env python3
"""Validate physical lane recovery and real post-tessellation SIMD shuffles."""
from pathlib import Path
import os
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from tessellation_shaders import TES_LANE_HELPER
source='''#include <metal_stdlib>
using namespace metal;
'''+TES_LANE_HELPER+'''
kernel void verify_compute(device atomic_uint* s [[buffer(0)]],uint native [[thread_index_in_simdgroup]],uint3 g [[thread_position_in_grid]]) {
    if ((g.x/32)%2==0 || native%3!=1) {
        uint lane=dm_tess_lane_id();
        atomic_fetch_add_explicit(s,1u,memory_order_relaxed);
        if(lane!=native)atomic_fetch_add_explicit(s+1,1u,memory_order_relaxed);
        if((g.x/32)%2)atomic_fetch_add_explicit(s+2,1u,memory_order_relaxed);
    }
}
struct O {float4 position [[position]];};
fragment float4 verify_fs(){return float4(1,0,0,1);}
[[patch(triangle,3)]] vertex O verify_tes(float3 uv [[position_in_patch]],device atomic_uint*s [[buffer(0)]]) {
    uint lane=dm_tess_lane_id();ulong active=ulong(simd_vote::vote_t(simd_ballot(true)));
    uint target=(lane&~3u)|3u;uint value=simd_shuffle(lane*17u+11u,ushort(target));
    bool valid=lane<32u;
    if((active>>target)&1ul){valid=valid && value==target*17u+11u;atomic_fetch_add_explicit(s+5,1u,memory_order_relaxed);}
    atomic_fetch_add_explicit(s+3,1u,memory_order_relaxed);
    if(!valid)atomic_fetch_add_explicit(s+4,1u,memory_order_relaxed);
    O o;o.position=float4(uv.xy*2.0-1.0,0,1);return o;
}
'''
path=ROOT/'work/test-tes-subgroup.metal';path.write_text(source)
binary=ROOT/'work/test-tes-subgroup'
subprocess.run(['clang','-O1','-g','-fobjc-arc',str(ROOT/'tests/test_tes_subgroup.m'),'-framework','Foundation','-framework','Metal','-o',str(binary)],check=True)
subprocess.run([str(binary),str(path)],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True)
