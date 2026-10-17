#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=2)return 2;id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError *err=nil;
 NSString *src=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&err];
 id<MTLLibrary>lib=[d newLibraryWithSource:src options:nil error:&err];if(!lib){fprintf(stderr,"%s\n",err.description.UTF8String);return 1;}
 MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"v"];pd.fragmentFunction=[lib newFunctionWithName:@"main0"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
 id<MTLRenderPipelineState>ps=[d newRenderPipelineStateWithDescriptor:pd error:&err];if(!ps)return 3;
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:3 height:2 mipmapped:NO];td.storageMode=MTLStorageModeShared;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>color=[d newTextureWithDescriptor:td];
 td.pixelFormat=MTLPixelFormatR32Float;td.usage=MTLTextureUsageShaderRead;id<MTLTexture>stored=[d newTextureWithDescriptor:td];
 float depth[6]={0.2f,0.3f,0.5f,NAN,0.1f,1.0f};[stored replaceRegion:MTLRegionMake2D(0,0,3,2) mipmapLevel:0 withBytes:depth bytesPerRow:12];
 id<MTLBuffer>counter=[d newBufferWithLength:4 options:MTLResourceStorageModeShared];id<MTLCommandQueue>q=[d newCommandQueue];
 float cases[4][4]={{1,0.2f,0.3f,0},{1,0.3f,0.2f,0},{0,0.2f,0.3f,0},{1,0,1,0}};
 for(int c=0;c<4;c++){
  *(uint32_t *)counter.contents=0;id<MTLCommandBuffer>cb=[q commandBuffer];MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.colorAttachments[0].texture=color;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:rp];[e setRenderPipelineState:ps];[e setFragmentBytes:cases[c] length:16 atIndex:26];[e setFragmentBuffer:counter offset:0 atIndex:1];[e setFragmentTexture:stored atIndex:0];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[e endEncoding];[cb commit];[cb waitUntilCompleted];
  uint8_t pixels[24];[color getBytes:pixels bytesPerRow:12 fromRegion:MTLRegionMake2D(0,0,3,2) mipmapLevel:0];unsigned expected=0;
  for(int i=0;i<6;i++){int pass=!cases[c][0] || (depth[i]>=cases[c][1] && depth[i]<=cases[c][2]);expected+=pass;if((pixels[4*i]!=0)!=pass || cb.error){fprintf(stderr,"stored-depth mismatch case=%d pixel=%d\n",c,i);return 1;}}
  if(*(uint32_t *)counter.contents!=expected){fprintf(stderr,"rejected fragment performed a side effect\n");return 1;}
 }
 puts("Metal stored-depth bounds: 24 pixels passed; incoming depth differs, inclusive limits/NaN/disable/side effects verified");
}return 0;}
