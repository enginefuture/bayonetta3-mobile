#pragma once
// GPU count stays on the GPU timeline. Slots beyond min(count,max) become
// zero-count native Metal indirect draws, preserving argument/base-ID layout.
static const char *nvn55_indirect_msl=
"#include <metal_stdlib>\nusing namespace metal;\n"
"kernel void prepare(device const uint* src [[buffer(0)]],device const uint* count [[buffer(1)]],device uint* dst [[buffer(2)]],constant uint4& p [[buffer(3)]],uint i [[thread_position_in_grid]]){"
"if(i>=p.x)return;uint n=min(*count,p.x);for(uint w=0;w<p.z;w++)dst[i*p.z+w]=i<n?src[i*p.y+w]:0u;}\n";

// Sources/counts are still read on the GPU. The replay planner only groups
// requests across commands proven not to write any input. Each request owns
// its output interval, so no inter-request barrier is necessary.
static const char *nvn55_indirect_batch_msl=
"#include <metal_stdlib>\nusing namespace metal;\n"
"struct Request {device const uint* src;device const uint* count;device uint* dst;uint maximum,stride,words,pad;};\n"
"kernel void prepare_batch(device const Request* requests [[buffer(0)]],constant uint& size [[buffer(1)]],uint r [[thread_position_in_grid]]){"
"if(r>=size)return;Request p=requests[r];uint n=min(*p.count,p.maximum);"
"for(uint i=0;i<p.maximum;i++)for(uint w=0;w<p.words;w++)p.dst[i*p.words+w]=i<n?p.src[i*p.stride+w]:0u;}\n";
