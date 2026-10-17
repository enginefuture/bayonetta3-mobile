// Exercise the production MetalFX encoder and Metal 4 GPU event bridge, including residency and color mode.
#import <Metal/Metal.h>
#import <MetalFX/MetalFX.h>
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <math.h>
#ifdef DM_TEST_IOS_SIZE
#undef TARGET_OS_IPHONE
#define TARGET_OS_IPHONE 1
#endif
#define DM_NVN_M3 0
#define CBUF id<MTL4CommandBuffer>
#define BENC id<MTL4ComputeCommandEncoder>
#define MLOG(...) do {fprintf(stderr,__VA_ARGS__);fputc('\n',stderr);}while(0)
#define MDIE(...) do {MLOG(__VA_ARGS__);abort();}while(0)
static id<MTLDevice> g_dev;
static id<MTLCommandQueue> g_q;
static id<MTL4CommandQueue> g_q4;
static id<MTLResidencySet> resident;
static void res_add(id<MTLResource> r){[resident addAllocation:r];}
static void res_remove(id<MTLResource> r){[resident removeAllocation:r];}
static void res_commit(void){[resident commit];}
static BENC enc_b_begin(CBUF cb){return [cb computeCommandEncoder];}
static void enc_b_end(BENC en){[en endEncoding];}
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_metalfx.inc"
int main(void){@autoreleasepool{
    setenv("DM_METALFX","spatial",1);assert(metalfx_enabled());
    g_dev=MTLCreateSystemDefaultDevice();g_q=[g_dev newCommandQueue];NSError *e=nil;
    resident=[g_dev newResidencySetWithDescriptor:[MTLResidencySetDescriptor new] error:&e];assert(resident);[resident requestResidency];
    id<MTL4CommandQueue> q=[g_dev newMTL4CommandQueueWithDescriptor:[MTL4CommandQueueDescriptor new] error:&e];assert(q);g_q4=q;[q addResidencySet:resident];
#ifdef DM_TEST_IOS_SIZE
    const int iw=1600,ih=900,active_w=1280,active_h=720;
#else
    const int iw=1920,ih=1080,active_w=iw,active_h=ih;
#endif
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:iw height:ih mipmapped:NO];
    td.storageMode=MTLStorageModeShared;td.usage=MTLTextureUsageShaderRead;
    id<MTLTexture> src=[g_dev newTextureWithDescriptor:td];assert(src);res_add(src);
    uint8_t *p=malloc(iw*ih*4);const uint8_t levels[]={0,32,64,128,192,255};
    for(int y=0;y<ih;y++)for(int x=0;x<iw;x++){int i=(y*iw+x)*4;for(int c=0;c<3;c++)p[i+c]=(x<active_w&&y<active_h)?levels[x*6/active_w]:(c==1?0:255);p[i+3]=255;}
    [src replaceRegion:MTLRegionMake2D(0,0,iw,ih) mipmapLevel:0 withBytes:p bytesPerRow:iw*4];free(p);
    id<MTLBuffer> rb=[g_dev newBufferWithLength:3840*2160*4 options:MTLResourceStorageModeShared];res_add(rb);
    id<MTL4CommandAllocator> allocator=[g_dev newCommandAllocatorWithDescriptor:[MTL4CommandAllocatorDescriptor new] error:&e];assert(allocator);
    CBUF cb=[g_dev newCommandBuffer];
    // Reuse every output slot after GPU completion, just as the presenter does.
    for(int frame=0;frame<6;frame++){
        [allocator reset];[cb beginCommandBufferWithAllocator:allocator];
#ifdef DM_TEST_IOS_SIZE
        // Recreate all slots after a native drawable resize; never allocate 4K.
        const int cw=frame<3?2736:2340,ch=frame<3?1260:1080,ow=frame<3?2240:1920,oh=ch;
#else
        const int cw=3840,ch=2160,ow=3840,oh=2160;
#endif
        id<MTLTexture> out=metalfx_spatial(cb,src,frame%3,cw,ch,active_w,active_h);assert(out.width==ow&&out.height==oh&&out.storageMode==MTLStorageModePrivate);
        BENC bl=enc_b_begin(cb);[bl barrierAfterQueueStages:MTLStageAll beforeStages:MTLStageAll visibilityOptions:MTL4VisibilityOptionDevice];
        [bl copyFromTexture:out sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(ow,oh,1) toBuffer:rb destinationOffset:0 destinationBytesPerRow:ow*4 destinationBytesPerImage:ow*oh*4];enc_b_end(bl);[cb endCommandBuffer];res_commit();
        dispatch_semaphore_t done=dispatch_semaphore_create(0);MTL4CommitOptions *options=[MTL4CommitOptions new];
        [options addFeedbackHandler:^(id<MTL4CommitFeedback> feedback){assert(!feedback.error);dispatch_semaphore_signal(done);}];
        CBUF buffers[]={cb};[q commit:buffers count:1 options:options];assert(dispatch_semaphore_wait(done,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC))==0);
        const uint8_t *outp=rb.contents;
        for(int y=100;y<oh;y+=300)for(int k=0;k<6;k++)for(int c=0;c<3;c++)assert(abs((int)outp[(y*ow+(2*k+1)*ow/12)*4+c]-levels[k])<=3);
    }
    puts("MetalFX production spatial encoder and Metal 4 event bridge: platform dimensions, perceptual gray levels, 3-slot reuse and resize passed");
}return 0;}
