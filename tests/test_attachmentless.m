#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=2)return 2;id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError *error=nil;
 NSString *src=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&error];id<MTLLibrary>lib=[d newLibraryWithSource:src options:nil error:&error];
 if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
 MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"v"];pd.fragmentFunction=[lib newFunctionWithName:@"main0"];pd.rasterSampleCount=1;
 id<MTLRenderPipelineState>pipeline=[d newRenderPipelineStateWithDescriptor:pd error:&error];if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
 id<MTLBuffer>count=[d newBufferWithLength:4 options:MTLResourceStorageModeShared];id<MTLCommandQueue>q=[d newCommandQueue];
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:1 height:1 mipmapped:NO];td.usage=MTLTextureUsageShaderRead;id<MTLTexture>dummy=[d newTextureWithDescriptor:td];
 for(int test=0;test<3;test++){
  NSUInteger w=test?4:1,h=test?3:1;*(uint32_t *)count.contents=0;
  MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.renderTargetWidth=w;rp.renderTargetHeight=h;rp.defaultRasterSampleCount=1;
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:rp];[e setRenderPipelineState:pipeline];[e setViewport:(MTLViewport){0,0,w,h,0,1}];
  if(test==2)[e setScissorRect:(MTLScissorRect){1,1,2,1}];uint32_t alpha[2]={8,0};float bounds[4]={0};[e setFragmentBuffer:count offset:0 atIndex:1];[e setFragmentBytes:alpha length:8 atIndex:27];[e setFragmentBytes:bounds length:16 atIndex:26];[e setFragmentTexture:dummy atIndex:0];
  [e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[e endEncoding];[cb commit];[cb waitUntilCompleted];uint32_t expected=test==2?2:(uint32_t)(w*h);
  if(cb.error || *(uint32_t *)count.contents!=expected){fprintf(stderr,"attachmentless case %d expected=%u got=%u error=%s\n",test,expected,*(uint32_t *)count.contents,cb.error.description.UTF8String);return 1;}
 }
 puts("Metal attachmentless raster: 3 GPU cases passed; viewport/scissor and fragment storage writes without color/depth attachments");
}return 0;}
