#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_indirect.h"
int main(void){@autoreleasepool{
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError *error=nil;
 NSString *source=[@(nvn55_indirect_msl) stringByAppendingString:@"\nkernel void seed(device uint* count [[buffer(0)]],constant uint& n [[buffer(1)]]){*count=n;}\n"];
 id<MTLLibrary>lib=[d newLibraryWithSource:source options:nil error:&error];if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
 id<MTLComputePipelineState>prepare=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"prepare"] error:&error],seed=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"seed"] error:&error];if(!prepare || !seed)return 2;
 uint32_t src[21];for(int i=0;i<21;i++)src[i]=100+i;src[3]=(uint32_t)-7;
 id<MTLBuffer>args=[d newBufferWithBytes:src length:sizeof src options:MTLResourceStorageModeShared],count=[d newBufferWithLength:4 options:MTLResourceStorageModeShared],out=[d newBufferWithLength:64 options:MTLResourceStorageModeShared];
 id<MTLCommandQueue>q=[d newCommandQueue];uint32_t counts[]={0,1,3,99};
 for(uint32_t words=4;words<=5;words++)for(int c=0;c<4;c++){
  *(uint32_t *)count.contents=0xdeadbeef;memset(out.contents,0xcd,64);uint32_t p[4]={3,7,words,0};id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
  [e setComputePipelineState:seed];[e setBuffer:count offset:0 atIndex:0];[e setBytes:&counts[c] length:4 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e memoryBarrierWithScope:MTLBarrierScopeBuffers];
  [e setComputePipelineState:prepare];[e setBuffer:args offset:0 atIndex:0];[e setBuffer:count offset:0 atIndex:1];[e setBuffer:out offset:0 atIndex:2];[e setBytes:p length:16 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[e endEncoding];[cb commit];[cb waitUntilCompleted];
  if(cb.error){fprintf(stderr,"%s\n",cb.error.description.UTF8String);return 3;}
  uint32_t *actual=out.contents;for(uint32_t i=0;i<3;i++)for(uint32_t w=0;w<words;w++){uint32_t expected=i<counts[c]?src[i*7+w]:0;if(actual[i*words+w]!=expected){fprintf(stderr,"indirect GPU count mismatch words=%u count=%u slot=%u word=%u\n",words,counts[c],i,w);return 4;}}
  if(actual[3*words]!=0xcdcdcdcd)return 5;
 }
 puts("GPU indirect-count preparation: 8 array/index cases passed; GPU-written counts, clamp, stride, signed base vertex, zero slots and write bounds verified");
}return 0;}
