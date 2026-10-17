// Exact captured depth-linearization shader ABI for this title. Unknown passes,
// movies and menus fail closed: they supply no interpolation inputs.
typedef struct {id<MTLTexture> depth;float near_z,far_z,fov,aspect,view[16];uint64_t frame;int valid;} dmfx_input;
static dmfx_input g_fx_inputs[16];
static pthread_mutex_t g_fx_input_mu=PTHREAD_MUTEX_INITIALIZER;
static int metalfx_frame_requested(void){const char *e=getenv("DM_FRAME_GENERATION");return e&&!strcmp(e,"metal");}
static dmfx_input metalfx_input_for_frame(uint64_t frame){pthread_mutex_lock(&g_fx_input_mu);dmfx_input x=g_fx_inputs[frame%16];pthread_mutex_unlock(&g_fx_input_mu);if(x.frame!=frame)x.valid=0;return x;}
static void metalfx_capture_inputs(NvProg *pr){
    if(!metalfx_frame_requested()||!pr->sh[1]||strncmp(pr->sh[1]->key,"2397737d7a7536d3_b",18))return;
    uint64_t frame=atomic_load(&g_cur_frame);int slot=frame%16;
    const p_bind_buf *u=&S.ubo[1][0];void *buffer;uint64_t off;
    if(u->size<42*16||pend_hits(u->addr,42*16)||!mtl_addr(u->addr,42*16,&buffer,&off))return;
    const float *camera=(const float *)((uint8_t *)[(__bridge id<MTLBuffer>)buffer contents]+off);
    dmfx_input x={0};x.near_z=camera[41*4];x.far_z=x.near_z+camera[41*4+1];
    x.fov=2*atanf(1/camera[5*4+1])*180/M_PI;x.aspect=camera[5*4+1]/camera[4*4];
    if(!(x.near_z>0 && x.far_z>x.near_z && x.fov>5 && x.fov<175 && fabsf(x.aspect-16.0f/9)<.02f) ||
       fabsf(camera[6*4+2]+x.far_z/(x.far_z-x.near_z))>1e-4f ||
       fabsf(camera[6*4+3]+x.far_z*x.near_z/(x.far_z-x.near_z))>1e-4f)return;
    pthread_mutex_lock(&g_rmu);id<MTLTexture> depth=tex_by_id(tid_handle(S.tex[1][8]));pthread_mutex_unlock(&g_rmu);
    if(depth.width!=1920||depth.height!=1080||depth.textureType!=MTLTextureType2D||depth.sampleCount!=1||
       (depth.pixelFormat!=MTLPixelFormatDepth32Float && depth.pixelFormat!=MTLPixelFormatDepth32Float_Stencil8))return;
    // At most eight queued presents and three in-flight frames; sixteen depth
    // slots outlive their consumers. Each slot is written once per guest frame.
    static id<MTLTexture> snapshots[16];static id<MTLBuffer> staging[16];
    if(!snapshots[slot]){
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:1920 height:1080 mipmapped:NO];d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageShaderRead;
        snapshots[slot]=[g_dev newTextureWithDescriptor:d];staging[slot]=[g_dev newBufferWithLength:1920*1080*4 options:MTLResourceStorageModePrivate];
        if(!snapshots[slot]||!staging[slot])MDIE("MetalFX frame depth snapshot allocation");res_add(snapshots[slot]);res_add(staging[slot]);
    }
    rp_end();BENC en=blit();
    [en copyFromTexture:depth sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(1920,1080,1) toBuffer:staging[slot] destinationOffset:0 destinationBytesPerRow:1920*4 destinationBytesPerImage:0 options:depth.pixelFormat==MTLPixelFormatDepth32Float_Stencil8?MTLBlitOptionDepthFromDepthStencil:MTLBlitOptionNone];
    en=blit();enc_b_copy_buffer_texture(en,staging[slot],0,1920*4,1920*1080*4,MTLSizeMake(1920,1080,1),snapshots[slot],0,0,MTLOriginMake(0,0,0));
    x.depth=snapshots[slot];memcpy(x.view,camera,sizeof x.view);x.valid=1;x.frame=frame;
    pthread_mutex_lock(&g_fx_input_mu);g_fx_inputs[slot]=x;pthread_mutex_unlock(&g_fx_input_mu);
    static int once;if(!once++)MLOG("MetalFX frame inputs: actual 1920x1080 depth near=%g far=%g FOV=%g aspect=%g; image-motion experimental",x.near_z,x.far_z,x.fov,x.aspect);
}
