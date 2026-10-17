#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=2)return 2;id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError *err=nil;
 NSString *src=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&err];
 id<MTLLibrary>lib=[d newLibraryWithSource:src options:nil error:&err];if(!lib){fprintf(stderr,"%s\n",err.description.UTF8String);return 1;}
 MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"v"];pd.fragmentFunction=[lib newFunctionWithName:@"main0"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
 id<MTLRenderPipelineState>ps=[d newRenderPipelineStateWithDescriptor:pd error:&err];if(!ps)return 3;
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:1 height:1 mipmapped:NO];td.storageMode=MTLStorageModeShared;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>tex=[d newTextureWithDescriptor:td];
 id<MTLCommandQueue>q=[d newCommandQueue];float refs[]={0.25f,0.5f,0.75f,NAN};int count=0;
 for(int j=0;j<4;j++)for(uint32_t f=1;f<=8;f++){
  float r=refs[j],a=0.5f;int pass=f==8 || (f==2&&a<r)||(f==3&&a==r)||(f==4&&a<=r)||(f==5&&a>r)||(f==6&&a!=r)||(f==7&&a>=r);
  uint32_t state[2]={f,0};memcpy(state+1,&r,4);id<MTLCommandBuffer>cb=[q commandBuffer];MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.colorAttachments[0].texture=tex;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
  id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:rp];[e setRenderPipelineState:ps];[e setFragmentBytes:state length:8 atIndex:27];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[e endEncoding];[cb commit];[cb waitUntilCompleted];
  uint8_t pixel[4];[tex getBytes:pixel bytesPerRow:4 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];if(cb.error || (pixel[0]!=0)!=pass){fprintf(stderr,"alpha mismatch f=%u ref=%g red=%u\n",f,r,pixel[0]);return 1;}count++;
 }
 printf("Metal alpha test: %d compare/boundary/NaN cases passed\n",count);
}return 0;}
