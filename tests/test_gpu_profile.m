#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <assert.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_gpu_profile.h"
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=2)return 2;setenv("DM_GPU_PASS_PROFILE",argv[1],1);setenv("DM_GPU_PASS_EVERY","1",1);
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError*error=nil;
 id<MTLLibrary>lib=[d newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;kernel void k(device uint* p [[buffer(0)]]){p[0]=42;} vertex float4 v(uint i [[vertex_id]]){float2 q[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(q[i],0,1);} fragment float4 f(){return float4(1,0,0,1);}" options:nil error:&error];
 id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&error];assert(p);
 id<MTL4CommandQueue>q=[d newMTL4CommandQueueWithDescriptor:[MTL4CommandQueueDescriptor new] error:&error];assert(q);
 id<MTL4CommandAllocator>a=[d newCommandAllocatorWithDescriptor:[MTL4CommandAllocatorDescriptor new] error:&error];assert(a);
 MTL4ArgumentTableDescriptor*td=[MTL4ArgumentTableDescriptor new];td.maxBufferBindCount=1;
 id<MTL4ArgumentTable>table=[d newArgumentTableWithDescriptor:td error:&error];assert(table);
 id<MTLBuffer>b=[d newBufferWithLength:4 options:MTLResourceStorageModeShared];[table setAddress:b.gpuAddress atIndex:0];
 MTLResidencySetDescriptor*rd=[MTLResidencySetDescriptor new];rd.initialCapacity=1;
 id<MTLResidencySet>rs=[d newResidencySetWithDescriptor:rd error:&error];assert(rs);[rs addAllocation:b];[rs commit];[q addResidencySet:rs];
 MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"v"];pd.fragmentFunction=[lib newFunctionWithName:@"f"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
 id<MTLRenderPipelineState>rpso=[d newRenderPipelineStateWithDescriptor:pd error:&error];assert(rpso);
 MTLTextureDescriptor*texd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];texd.usage=MTLTextureUsageRenderTarget;texd.storageMode=MTLStorageModeShared;
 id<MTLTexture>texture=[d newTextureWithDescriptor:texd];assert(texture);[rs addAllocation:texture];[rs commit];
 for(unsigned iteration=0;iteration<3;iteration++){
  [a reset];id<MTL4CommandBuffer>cb=[d newCommandBuffer];[cb beginCommandBufferWithAllocator:a];
  dm_gpu_profile_submit(d,0);
  id<MTL4ComputeCommandEncoder>e=[cb computeCommandEncoder];
  dm_gpu_profile_begin(e,'C',iteration,0,0);[e setComputePipelineState:p];[e setArgumentTable:table];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];dm_gpu_profile_end(e);[e endEncoding];
  MTL4RenderPassDescriptor*rp=[MTL4RenderPassDescriptor new];rp.colorAttachments[0].texture=texture;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTL4RenderCommandEncoder>re=[cb renderCommandEncoderWithDescriptor:rp];dm_gpu_profile_begin(re,'R',iteration,4,4);[re setRenderPipelineState:rpso];[re setViewport:(MTLViewport){0,0,4,4,0,1}];[re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];dm_gpu_profile_end(re);[re endEncoding];
  dispatch_block_t resolve=dm_gpu_profile_seal();assert(resolve);[cb endCommandBuffer];
  dispatch_semaphore_t done=dispatch_semaphore_create(0);__block int failed=0;
  MTL4CommitOptions*options=[MTL4CommitOptions new];[options addFeedbackHandler:^(id<MTL4CommitFeedback>f){failed=!!f.error;resolve();dispatch_semaphore_signal(done);}];
  id<MTL4CommandBuffer>buffers[]={cb};[q commit:buffers count:1 options:options];
  assert(!dispatch_semaphore_wait(done,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC)));assert(!failed);assert(*(uint32_t*)b.contents==42);uint8_t pixels[64];[texture getBytes:pixels bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];assert(pixels[0]==255 && pixels[1]==0 && pixels[3]==255);
 }
 NSString*text=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&error];assert(text);
 int rows=0;for(NSString*line in [text componentsSeparatedByString:@"\n"]){if(!line.length||[line hasPrefix:@"#"]||[line hasPrefix:@"frame"])continue;NSArray*c=[line componentsSeparatedByString:@"\t"];assert(c.count==9);assert([c[7] longLongValue]>0);assert([c[8] longLongValue]>=[c[7] longLongValue]);rows++;}assert(rows==6);
 puts("Metal4 GPU profiling: real render/compute readback, timestamp resolution and allocator reuse passed");
}return 0;}
