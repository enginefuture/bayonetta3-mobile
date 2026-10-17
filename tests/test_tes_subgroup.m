#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <assert.h>

int main(int argc,const char **argv){@autoreleasepool{
    assert(argc==2);NSError *error=nil;id<MTLDevice>device=MTLCreateSystemDefaultDevice();assert(device);
    NSString*source=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&error];assert(source);
    id<MTLLibrary>library=[device newLibraryWithSource:source options:nil error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
    id<MTLCommandQueue>queue=[device newCommandQueue];
    id<MTLBuffer>stats=[device newBufferWithLength:64 options:MTLResourceStorageModeShared];
    id<MTLComputePipelineState>compute=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"verify_compute"] error:&error];assert(compute);
    id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];[ce setComputePipelineState:compute];[ce setBuffer:stats offset:0 atIndex:0];[ce dispatchThreadgroups:MTLSizeMake(4,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[ce endEncoding];
    // The compute kernel compares against Apple's independent native lane ID,
    // including branches with non-contiguous active-lane masks.
    [cb commit];[cb waitUntilCompleted];assert(!cb.error);uint32_t*p=stats.contents;assert(p[0]>0&&p[1]==0&&p[2]>0);
    MTLRenderPipelineDescriptor*d=[MTLRenderPipelineDescriptor new];d.vertexFunction=[library newFunctionWithName:@"verify_tes"];d.fragmentFunction=[library newFunctionWithName:@"verify_fs"];d.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;d.inputPrimitiveTopology=MTLPrimitiveTopologyClassTriangle;d.maxTessellationFactor=64;d.tessellationPartitionMode=MTLTessellationPartitionModeInteger;d.tessellationFactorFormat=MTLTessellationFactorFormatHalf;d.tessellationControlPointIndexType=MTLTessellationControlPointIndexTypeNone;d.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionPerPatch;d.tessellationOutputWindingOrder=MTLWindingCounterClockwise;
    id<MTLRenderPipelineState>pipeline=[device newRenderPipelineStateWithDescriptor:d error:&error];if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
    id<MTLBuffer>factors=[device newBufferWithLength:17*sizeof(MTLTriangleTessellationFactorsHalf) options:MTLResourceStorageModeShared];MTLTriangleTessellationFactorsHalf*f=factors.contents;
    for(int i=0;i<17;i++){__fp16 value=(i%8)+1;for(int j=0;j<3;j++)memcpy(&f[i].edgeTessellationFactor[j],&value,2);memcpy(&f[i].insideTessellationFactor,&value,2);}
    MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageRenderTarget;pass.colorAttachments[0].texture=[device newTextureWithDescriptor:td];pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionDontCare;
    cb=[queue commandBuffer];id<MTLRenderCommandEncoder>re=[cb renderCommandEncoderWithDescriptor:pass];[re setRenderPipelineState:pipeline];[re setVertexBuffer:stats offset:0 atIndex:0];[re setTessellationFactorBuffer:factors offset:0 instanceStride:0];[re drawPatches:3 patchStart:0 patchCount:17 patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:1 baseInstance:0];[re endEncoding];[cb commit];[cb waitUntilCompleted];assert(!cb.error);
    fprintf(stderr,"stats: compute=%u bad=%u holes=%u tes=%u bad=%u shuffles=%u\n",p[0],p[1],p[2],p[3],p[4],p[5]);
    assert(p[3]>100&&p[4]==0&&p[5]>0);printf("Physical TES subgroup: compute=%u holes=%u TES=%u shuffles=%u, errors=0\n",p[0],p[2],p[3],p[5]);
}return 0;}
