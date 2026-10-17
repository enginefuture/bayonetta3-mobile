#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#import <MetalFX/MetalFX.h>
#include <assert.h>
#include <stdio.h>
#define MDIE(...) do{fprintf(stderr,__VA_ARGS__);abort();}while(0)
static id<MTLDevice>g_dev;
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_metalfx_flow.inc"
int main(void){@autoreleasepool{
 g_dev=MTLCreateSystemDefaultDevice();id<MTLCommandQueue>q=[g_dev newCommandQueue];
 int w=1920,h=1080;MTLTextureDescriptor*d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:w height:h mipmapped:NO];d.storageMode=MTLStorageModeShared;d.usage=MTLTextureUsageShaderRead;
 id<MTLTexture>colors[3];uint8_t*p=malloc(w*h*4);
 for(int f=0;f<3;f++){colors[f]=[g_dev newTextureWithDescriptor:d];for(int y=0;y<h;y++)for(int x=0;x<w;x++){
  int xx=x-f*16;unsigned hash=(unsigned)(xx/8)*73856093u^(unsigned)(y/8)*19349663u;hash^=hash>>13;hash*=1274126177u;unsigned v=(xx>=400&&xx<1000&&y>=300&&y<780)?(32+hash%200):0;
  for(int c=0;c<3;c++)p[(y*w+x)*4+c]=v;p[(y*w+x)*4+3]=255;
 }[colors[f] replaceRegion:MTLRegionMake2D(0,0,w,h) mipmapLevel:0 withBytes:p bytesPerRow:w*4];}free(p);
 id<MTLBuffer>rb=[g_dev newBufferWithLength:w*h*4 options:MTLResourceStorageModeShared];
 for(int f=0;f<4;f++){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLTexture>motion=metalfx_motion(cb,colors[1],colors[0]);
  id<MTLBlitCommandEncoder>bl=[cb blitCommandEncoder];[bl copyFromTexture:motion sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(w,h,1) toBuffer:rb destinationOffset:0 destinationBytesPerRow:w*4 destinationBytesPerImage:w*h*4];[bl endEncoding];[cb commit];[cb waitUntilCompleted];assert(!cb.error);
  const __fp16*v=rb.contents;double sum=0,bg=0;int n=0;for(int y=380;y<700;y+=8)for(int x=500;x<900;x+=8){sum+=v[(y*w+x)*2];bg+=v[(y*w+x)*2+1];n++;}printf("GPU flow %.3fms mean dx=%.3f dy=%.3f expected -16,0\n",(cb.GPUEndTime-cb.GPUStartTime)*1000,sum/n,bg/n);int good=0;float xs[2000],ys[2000];int k=0;
  for(int y=380;y<700;y+=8)for(int x=500;x<900;x+=8){xs[k]=v[(y*w+x)*2];ys[k]=v[(y*w+x)*2+1];good+=fabs(xs[k]+16)<2&&fabs(ys[k])<2;k++;}
  for(int i=1;i<k;i++){float x=xs[i],y=ys[i];int j=i-1;while(j>=0&&xs[j]>x){xs[j+1]=xs[j];j--;}xs[j+1]=x;j=i-1;while(j>=0&&ys[j]>y){ys[j+1]=ys[j];j--;}ys[j+1]=y;}
  printf("motion accuracy %d/%d median %.3f,%.3f (experimental; outliers retained in report)\n",good,n,xs[k/2],ys[k/2]);assert(good>=n*.90&&fabs(xs[k/2]+16)<.5&&fabs(ys[k/2])<.5);
 }
 // A known planar synthetic scene supplies real camera/depth/motion metadata.
 // This verifies the Apple interpolator, not Bayonetta skeletal motion support.
 MTLFXFrameInterpolatorDescriptor *fd=[MTLFXFrameInterpolatorDescriptor new];fd.inputWidth=w;fd.inputHeight=h;fd.outputWidth=w;fd.outputHeight=h;fd.colorTextureFormat=MTLPixelFormatBGRA8Unorm;fd.outputTextureFormat=MTLPixelFormatBGRA8Unorm;fd.depthTextureFormat=MTLPixelFormatR32Float;fd.motionTextureFormat=MTLPixelFormatRG16Float;
 id<MTLFXFrameInterpolator> it=[fd newFrameInterpolatorWithDevice:g_dev];assert(it);
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:w height:h mipmapped:NO];td.storageMode=MTLStorageModeShared;td.usage=it.depthTextureUsage;id<MTLTexture> depth=[g_dev newTextureWithDescriptor:td];float *z=malloc(w*h*4);for(int i=0;i<w*h;i++)z[i]=.5;[depth replaceRegion:MTLRegionMake2D(0,0,w,h) mipmapLevel:0 withBytes:z bytesPerRow:w*4];free(z);
 td.pixelFormat=fd.outputTextureFormat;td.storageMode=MTLStorageModePrivate;td.usage=it.outputTextureUsage|MTLTextureUsageShaderRead;id<MTLTexture> result=[g_dev newTextureWithDescriptor:td];
 for(int frame=0;frame<3;frame++){int reset=frame==0;id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLTexture> mv=metalfx_motion(cb,colors[frame],colors[MAX(frame-1,0)]);
  it.colorTexture=colors[frame];it.prevColorTexture=colors[MAX(frame-1,0)];it.depthTexture=depth;it.motionTexture=mv;it.outputTexture=result;it.shouldResetHistory=reset;it.motionVectorScaleX=it.motionVectorScaleY=1;it.deltaTime=1.0/60;it.nearPlane=.1;it.farPlane=100;it.fieldOfView=60;it.aspectRatio=(float)w/h;it.depthReversed=NO;
  [it encodeToCommandBuffer:cb];id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];[bl copyFromTexture:result sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(w,h,1) toBuffer:rb destinationOffset:0 destinationBytesPerRow:w*4 destinationBytesPerImage:w*h*4];[bl endEncoding];[cb commit];[cb waitUntilCompleted];if(cb.error)fprintf(stderr,"%s\n",cb.error.description.UTF8String);assert(!cb.error);
  if(frame==2){double sum=0,moment=0;uint8_t *b=rb.contents;for(int y=0;y<h;y++)for(int x=0;x<w;x++){double v=b[(y*w+x)*4];sum+=v;moment+=v*x;}double cx=moment/fmax(sum,1);printf("MetalFX generated-frame centroid %.3f expected near 723.5 (previous 715.5 / current 731.5) GPU %.3fms\n",cx,(cb.GPUEndTime-cb.GPUStartTime)*1000);assert(cx>720&&cx<727);}
 }
}return 0;}
