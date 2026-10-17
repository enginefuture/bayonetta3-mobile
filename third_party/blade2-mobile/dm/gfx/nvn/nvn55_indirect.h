#pragma once
// GPU count stays on the GPU timeline. Slots beyond min(count,max) become
// zero-count native Metal indirect draws, preserving argument/base-ID layout.
static const char *nvn55_indirect_msl=
"#include <metal_stdlib>\nusing namespace metal;\n"
"kernel void prepare(device const uint* src [[buffer(0)]],device const uint* count [[buffer(1)]],device uint* dst [[buffer(2)]],constant uint4& p [[buffer(3)]],uint i [[thread_position_in_grid]]){"
"if(i>=p.x)return;uint n=min(*count,p.x);for(uint w=0;w<p.z;w++)dst[i*p.z+w]=i<n?src[i*p.y+w]:0u;}\n";
