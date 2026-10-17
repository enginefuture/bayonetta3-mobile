#include "nvn_metalfx_flow.inc"
static dmfx_input g_fx_present_input;
static id<MTLTexture> g_fx_generated[3];
static id<MTLTexture> metalfx_frame_encode(id<MTLCommandBuffer> cb,id<MTLTexture> upscaled,id<MTLTexture> low,int slot){
    static id<MTLFXFrameInterpolator> interpolator;
    static id<MTLTexture> history[3],previous_color,previous_low;
    static uint64_t previous_frame;static double previous_time;static float previous_fov;static unsigned warmup;
    g_fx_generated[slot]=nil;
    if(!metalfx_frame_requested())return nil;
    char screen[128];double hz=front_display_refresh(screen,sizeof screen);
    if(hz<100){static int once;if(!once++)MLOG("MetalFX frame generation inactive: display %s %.1f Hz (requires >=100 Hz)",screen,hz);warmup=0;return nil;}
    dmfx_input input=g_fx_present_input;
    if(!input.valid){warmup=0;previous_color=previous_low=nil;return nil;}
    if(!interpolator){
        if(![MTLFXFrameInterpolatorDescriptor supportsDevice:g_dev])MDIE("MetalFX frame interpolation unsupported on this device");
        MTLFXFrameInterpolatorDescriptor *d=[MTLFXFrameInterpolatorDescriptor new];d.inputWidth=1920;d.inputHeight=1080;d.outputWidth=3840;d.outputHeight=2160;
        d.colorTextureFormat=d.outputTextureFormat=MTLPixelFormatBGRA8Unorm;d.depthTextureFormat=MTLPixelFormatR32Float;d.motionTextureFormat=MTLPixelFormatRG16Float;
        interpolator=[d newFrameInterpolatorWithDevice:g_dev];if(!interpolator)MDIE("MetalFX frame interpolator creation failed");
        MLOG("MetalFX frame interpolation created; real depth/camera + GPU image motion; two history warmup frames; experimental");
    }
    if(!history[slot]){
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:low.pixelFormat width:1920 height:1080 mipmapped:NO];d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageShaderRead;history[slot]=[g_dev newTextureWithDescriptor:d];
        if(!history[slot])MDIE("MetalFX motion history allocation");
    }
    double time=CACurrentMediaTime(),dt=previous_time?time-previous_time:1.0/60;
    BOOL reset=!warmup || input.frame!=previous_frame+1 || dt>.05 || dt<.001 || fabsf(previous_fov-input.fov)>5;
    if(reset)warmup=0;
    id<MTLTexture> motion=metalfx_motion(cb,low,reset?low:previous_low);
    // The output slot remains alive until its real present ticket completes.
    static id<MTLTexture> outputs[3];
    if(!outputs[slot]){MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:3840 height:2160 mipmapped:NO];d.storageMode=MTLStorageModePrivate;d.usage=interpolator.outputTextureUsage|MTLTextureUsageShaderRead;outputs[slot]=[g_dev newTextureWithDescriptor:d];if(!outputs[slot])MDIE("MetalFX generated output allocation");}
    interpolator.colorTexture=upscaled;interpolator.prevColorTexture=reset?upscaled:previous_color;
    interpolator.depthTexture=input.depth;interpolator.motionTexture=motion;interpolator.outputTexture=outputs[slot];
    interpolator.nearPlane=input.near_z;interpolator.farPlane=input.far_z;interpolator.fieldOfView=input.fov;interpolator.aspectRatio=input.aspect;
    interpolator.depthReversed=NO;interpolator.deltaTime=dt;interpolator.motionVectorScaleX=interpolator.motionVectorScaleY=1;
    interpolator.shouldResetHistory=reset;[interpolator encodeToCommandBuffer:cb];
    id<MTLBlitCommandEncoder> copy=[cb blitCommandEncoder];[copy copyFromTexture:low sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(1920,1080,1) toTexture:history[slot] destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];[copy endEncoding];
    previous_color=upscaled;previous_low=history[slot];previous_frame=input.frame;previous_time=time;previous_fov=input.fov;
    if(++warmup>=3)g_fx_generated[slot]=outputs[slot];
    return g_fx_generated[slot];
}
