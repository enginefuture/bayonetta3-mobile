#if DM_BAYONETTA3
#include "nvn_metalfx_frame.inc"
#endif
// Presentation-thread owned. Each slot is reused only after its present ticket's
// GPU completion (the allocator fence in present_now), including the FX output.
static _Atomic int g_metalfx_enabled=-1;
static int metalfx_enabled(void) {
    int enabled=atomic_load(&g_metalfx_enabled);
    if(enabled<0){const char *e=getenv("DM_METALFX");enabled=e&&!strcmp(e,"spatial");atomic_store(&g_metalfx_enabled,enabled);}
    return enabled;
}
void mtl_set_metalfx(int enabled){atomic_store(&g_metalfx_enabled,enabled!=0);MLOG("MetalFX spatial %s (game rendering unchanged)",enabled?"on":"off");}
static id<MTLTexture> metalfx_spatial(CBUF cb, id<MTLTexture> src, int slot, NSUInteger canvas_w, NSUInteger canvas_h, NSUInteger content_w, NSUInteger content_h) {
static id<MTLFXSpatialScaler> scalers[3];
#if !DM_NVN_M3
    static id<MTLSharedEvent> bridge; static uint64_t bridge_tick;
#endif
    static id<MTLTexture> output[3];
#if TARGET_OS_IPHONE
    // Preserve the game's original handheld render targets/DRS. Upscale to the
    // native drawable's fitted content area, never the Mac's fixed 4K canvas.
    double scale=fmin((double)canvas_w/content_w,(double)canvas_h/content_h);
    NSUInteger ow=(NSUInteger)llround(content_w*scale),oh=(NSUInteger)llround(content_h*scale);
    if(scale<=1.0 || ![MTLFXSpatialScalerDescriptor supportsDevice:g_dev]) return nil;
#else
    (void)canvas_w;(void)canvas_h;
    NSUInteger ow=3840,oh=2160;
    if (src.width != 1920 || src.height != 1080)
        MDIE("MetalFX fixed-1080p contract failed: actual source %lux%lu",(unsigned long)src.width,(unsigned long)src.height);
#endif
    if (!scalers[slot] || scalers[slot].inputWidth!=src.width || scalers[slot].inputHeight!=src.height ||
        scalers[slot].outputWidth!=ow || scalers[slot].outputHeight!=oh || scalers[slot].colorTextureFormat!=src.pixelFormat) {
        // The present ticket has completed before this slot can be reused.
        if(output[slot]) { res_remove(output[slot]); output[slot]=nil; }
        scalers[slot]=nil;
        MTLFXSpatialScalerDescriptor *d = [MTLFXSpatialScalerDescriptor new];
        d.inputWidth=src.width; d.inputHeight=src.height; d.outputWidth=ow; d.outputHeight=oh;
        d.colorTextureFormat=src.pixelFormat; d.outputTextureFormat=MTLPixelFormatBGRA8Unorm;
        // present_src removes the sRGB view. These are perceptual scan-out bytes.
        d.colorProcessingMode=MTLFXSpatialScalerColorProcessingModePerceptual;
        if (![MTLFXSpatialScalerDescriptor supportsDevice:g_dev]) MDIE("MetalFX spatial unsupported on this device");
        scalers[slot]=[d newSpatialScalerWithDevice:g_dev];
        if (!scalers[slot]) MDIE("MetalFX spatial scaler creation failed");
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:d.outputTextureFormat width:ow height:oh mipmapped:NO];
        td.storageMode=MTLStorageModePrivate; td.usage=scalers[slot].outputTextureUsage|MTLTextureUsageShaderRead;
        output[slot]=[g_dev newTextureWithDescriptor:td];
        if (!output[slot]) MDIE("MetalFX output allocation failed");
        output[slot].label=[NSString stringWithFormat:@"MetalFX %lux%lu output %d",(unsigned long)ow,(unsigned long)oh,slot];
        res_add(output[slot]); res_commit();
        MLOG("MetalFX spatial slot=%d texture=%lux%lu content=%lux%lu output=%lux%lu perceptual format=%lu required-input-usage=%lu frame-generation=%s",
             slot,(unsigned long)src.width,(unsigned long)src.height,(unsigned long)content_w,(unsigned long)content_h,(unsigned long)ow,(unsigned long)oh,(unsigned long)src.pixelFormat,(unsigned long)scalers[slot].colorTextureUsage,getenv("DM_FRAME_GENERATION")?:"off");
    }
    if (src.pixelFormat!=scalers[slot].colorTextureFormat ||
        (src.usage & scalers[slot].colorTextureUsage)!=scalers[slot].colorTextureUsage)
        MDIE("MetalFX input format/usage changed or unsupported");
    // The original handheld mode crops 1280x720 from a 1600x900 allocation.
    // MetalFX's public content-size properties select that top-left region.
    scalers[slot].inputContentWidth=content_w; scalers[slot].inputContentHeight=content_h;
    scalers[slot].colorTexture=src; scalers[slot].outputTexture=output[slot];
#if DM_NVN_M3
    [scalers[slot] encodeToCommandBuffer:cb];
#else
    // SDK 27 removed the Metal4FX barrier-stage properties required by the
    // macOS 26 implementation. Use the public MetalFX encoder through an ordered
    // GPU event bridge; no CPU wait or undocumented selectors. The input has
    // finished rendering before FX reads it, and present waits for FX output.
    if (!bridge) bridge=[g_dev newSharedEvent];
    uint64_t ready=++bridge_tick, finished=++bridge_tick;
    [g_q4 signalEvent:bridge value:ready];
    id<MTLCommandBuffer> fx=[g_q commandBuffer];fx.label=@"MetalFX spatial upscale";
    [fx encodeWaitForEvent:bridge value:ready];
    [scalers[slot] encodeToCommandBuffer:fx];
#if DM_BAYONETTA3
    metalfx_frame_encode(fx,output[slot],src,slot);
#endif
    [fx encodeSignalEvent:bridge value:finished];
    [fx addCompletedHandler:^(id<MTLCommandBuffer> result){if(result.error) MDIE("MetalFX GPU error: %s",result.error.description.UTF8String);}];
    [fx commit];[g_q4 waitForEvent:bridge value:finished];
#endif
    return output[slot];
}
