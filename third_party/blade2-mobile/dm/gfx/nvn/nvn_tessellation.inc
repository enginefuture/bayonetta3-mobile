// Metal 4 has no patch draw API. Original translated VS/TCS execute as compute,
// then Metal's fixed-function tessellator executes the translated TES. The
// legacy island is ordered with the current Metal 4 submission and checked.
#define TITLE_TESS_POINT_BYTES (33*16)
static NSMutableDictionary<NSString *,NvShader *> *g_tess_shaders;
static NvShader *title_tess_shader(const char *key,const char *suffix,int stage){
    NSString *name=[NSString stringWithFormat:@"%.16s_%s",key,suffix];
    if(!g_tess_shaders)g_tess_shaders=[NSMutableDictionary dictionary];
    NvShader *have=g_tess_shaders[name];if(have)return have;
    const char *directory=getenv("DM_NVN_TESS_DIR");if(!directory)MDIE("Missing verified tessellation supplement; run tools/build_tessellation.py");
    NSError *error=nil;NSString *base=[@(directory) stringByAppendingPathComponent:name];
    id<MTLLibrary> lib=lib_from_file([base stringByAppendingString:@".metallib"],&error);
    NSData *data=[NSData dataWithContentsOfFile:[base stringByAppendingString:@".json"]];NSDictionary *j=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:&error]:nil;
    NSString *kind=stage==0?@"tess-vs":stage==3?@"tcs":@"tes";
    if(!lib || !j || ![j[@"key"] isEqual:name] || ![j[@"stage"] isEqual:kind] || ![j[@"route"] isEqual:@"B"] || ![j[@"tessellation_domain"] isEqual:@"triangle"] || ![j[@"chain"] isEqual:@DMSH_CHAIN] || [j[@"control_point_bytes"] intValue]!=TITLE_TESS_POINT_BYTES || [j[@"output_points"] intValue]!=3)
        MDIE("Invalid tessellation library %s: %s",name.UTF8String,error?error.description.UTF8String:"identity/ABI mismatch");
    NvShader *s=[NvShader new];char why[256];
    if(nvn_refl_from_json(j,&s->rf,why,sizeof why))MDIE("Tessellation reflection %s: %s",name.UTF8String,why);
    s->fn=[lib newFunctionWithName:j[@"entry"]];s->stage=stage;strlcpy(s->key,name.UTF8String,sizeof s->key);
    if(!s->fn)MDIE("Missing tessellation function %s",name.UTF8String);
    if(s->rf.nb){s->ae=[s->fn newArgumentEncoderWithBufferIndex:s->rf.abi];s->arg_len=s->ae.encodedLength;}
    if(s->rf.has_c1)c1_store(s);s->range_ro=rt_range_bindings_ro(j);g_tess_shaders[name]=s;return s;
}
static id<MTLComputePipelineState> title_tess_vertex_pipeline(NvShader *vs,BOOL indexed){
    static nvn_hmap cache={.klen=sizeof(pso_key)+sizeof(uint64_t)};
    struct {pso_key state;uint64_t indexed;} key={0};pso_key_fill(&key.state,vs,nil,(uint32_t[8]){0},0,0,1,0);key.indexed=indexed;
    id<MTLComputePipelineState> found=hm_get_id(&cache,&key);if(found)return found;
    MTLComputePipelineDescriptor *d=[MTLComputePipelineDescriptor new];d.computeFunction=vs->fn;
    MTLStageInputOutputDescriptor *input=[MTLStageInputOutputDescriptor stageInputOutputDescriptor];
    input.indexBufferIndex=1;input.indexType=MTLIndexTypeUInt32;
    for(int i=0;i<vs->rf.nv;i++){
        unsigned a=vs->rf.v[i].nvn,loc=vs->rf.v[i].loc;if(a>=16||loc>=32)MDIE("Tessellation vertex attribute range");
        MTLVertexFormat f=a<S.nattr?vfmt(S.attr[a].fmt):MTLVertexFormatInvalid;
        if(f==MTLVertexFormatInvalid)MDIE("Missing tessellation vertex input loc=%u NVN=%u format=%u",loc,a,S.attr[a].fmt);
        unsigned stream=S.attr[a].stream;if(stream>=14)MDIE("Tessellation stream overlaps reserved zero buffer");
        input.attributes[loc].format=(MTLAttributeFormat)f;input.attributes[loc].offset=S.attr[a].offset;input.attributes[loc].bufferIndex=16+stream;
        input.layouts[16+stream].stride=S.stream[stream].stride?:4;
        input.layouts[16+stream].stepFunction=!S.stream[stream].stride?MTLStepFunctionConstant:S.stream[stream].divisor?MTLStepFunctionThreadPositionInGridY:indexed?MTLStepFunctionThreadPositionInGridXIndexed:MTLStepFunctionThreadPositionInGridX;
        input.layouts[16+stream].stepRate=!S.stream[stream].stride?0:S.stream[stream].divisor?:1;
        attrfacts_note(vs,loc,S.attr[a].fmt);
    }
    d.stageInputDescriptor=input;NSError *error=nil;found=[g_dev newComputePipelineStateWithDescriptor:d options:0 reflection:nil error:&error];
    if(!found)MDIE("Tessellation VS pipeline %s: %s",vs->key,error.description.UTF8String);hm_put_id(&cache,&key,found);return found;
}
static id<MTLComputePipelineState> title_tess_control_pipeline(NvShader *tc){
    static nvn_hmap cache={.klen=sizeof(void *)};const void *key=(__bridge void *)tc;id<MTLComputePipelineState> ps=hm_get_id(&cache,&key);
    if(!ps){NSError *e=nil;ps=[g_dev newComputePipelineStateWithFunction:tc->fn error:&e];if(!ps)MDIE("TCS pipeline %s",e.description.UTF8String);hm_put_id(&cache,&key,ps);}return ps;
}
static void title_tess_draw(const p_draw *dw,const p_draw_idx *di){
    if(g_oq_open)g_oqi.nd_seen++;
    if(!S.prog)MDIE("Tessellation without a bound program");
    NvProg *pr=prog_get(S.prog);if(!pr->sh[0]||!pr->tesskeys[0][0]||!pr->tesskeys[1][0])MDIE("Tessellation requires original VS/TCS/TES");
    if(S.patch_size!=3)MDIE("Unverified tessellation patch size=%u",S.patch_size);
    if(g_defer_replaying)MDIE("Tessellation within deferred replay requires explicit lifetime validation");
    int count=dw?dw->count:di->count,instances=dw?dw->instances:di->instances;
    uint64_t indirect=dw?dw->indirect:di->indirect;
    if(indirect)MDIE("Indirect tessellation draw requires GPU argument conversion");
    if(count<0||instances<0||(dw&&dw->first<0)||(dw?dw->base_instance:di->base_instance)<0)MDIE("Invalid tessellation draw extent");if(!count)return;
    // The recorded non-instanced NVN commands use zero, matching ordinary draw().
    if(!instances)instances=1;
    if(count%3||count>3*1048576||instances>65535||(uint64_t)count*instances>3*1048576)MDIE("Tessellation extent unsupported: count=%d instances=%d",count,instances);
    unsigned patches=count/3,total=patches*instances,base=dw?dw->base_instance:di->base_instance;
    NSUInteger width,height;rt_dims(&width,&height);
    MTLScissorRect scissor={0,0,width,height};
    if(R.has_sc){int64_t x=MAX(R.sc.x,0),y=MAX(R.sc.y,0),x1=MIN((int64_t)R.sc.x+R.sc.w,(int64_t)width),y1=MIN((int64_t)R.sc.y+R.sc.h,(int64_t)height);
        // Supported control/vertex libraries have no external writes. An empty
        // raster region must not leave an uncommitted legacy encoder behind.
        if(x1<=x||y1<=y)return;scissor=(MTLScissorRect){x,y,x1-x,y1-y};}
    NvShader *vs=title_tess_shader(pr->sh[0]->key,"tv",0),*tc=title_tess_shader(pr->tesskeys[0],"tc",3),*te=title_tess_shader(pr->tesskeys[1],"te",4),*fs=pr->sh[1];
    if(S.color.logic_op!=NVN_LOGIC_OP_COPY)MDIE("Tessellation raster logic op unsupported");
    // Clear/store preceding attachments and materialize the actual stored depth
    // bounds before constructing the independent legacy pass.
    rp_flush();if(S.depth_bounds.enabled&&R.rt.depth)title_depth_snapshot();rp_end();
    MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];uint32_t formats[8]={0},df=0,sf=0;NSUInteger samples=1;BOOL any=NO;
    for(int i=0;i<R.rt.n&&i<8;i++)if(R.rt.color[i]){attach(pass.colorAttachments[i],R.rt.color[i],&R.rt.cview[i],R.rt.has_cview[i],1);pass.colorAttachments[i].loadAction=MTLLoadActionLoad;pass.colorAttachments[i].storeAction=MTLStoreActionStore;formats[i]=(uint32_t)pass.colorAttachments[i].texture.pixelFormat;samples=pass.colorAttachments[i].texture.sampleCount;any=YES;}
    if(R.rt.depth){attach(pass.depthAttachment,R.rt.depth,&R.rt.dview,R.rt.has_dview,0);df=(uint32_t)pass.depthAttachment.texture.pixelFormat;pass.depthAttachment.loadAction=MTLLoadActionLoad;pass.depthAttachment.storeAction=MTLStoreActionStore;samples=pass.depthAttachment.texture.sampleCount;any=YES;
        if(df==MTLPixelFormatDepth32Float_Stencil8){attach(pass.stencilAttachment,R.rt.depth,&R.rt.dview,R.rt.has_dview,0);pass.stencilAttachment.loadAction=MTLLoadActionLoad;pass.stencilAttachment.storeAction=MTLStoreActionStore;sf=df;}}
    if(!any)MDIE("Attachmentless tessellation requires explicit raster extent");
    pso_key rkey;pso_key_fill(&rkey,te,fs,formats,df,sf,(uint32_t)samples,0);
    static nvn_hmap render_cache={.klen=sizeof(pso_key)};id<MTLRenderPipelineState> raster=hm_get_id(&render_cache,&rkey);
    if(!raster){MTLRenderPipelineDescriptor *d=pso_desc(&rkey,te,fs,nil,0);d.vertexDescriptor=nil;d.inputPrimitiveTopology=MTLPrimitiveTopologyClassTriangle;d.tessellationPartitionMode=MTLTessellationPartitionModeInteger;d.maxTessellationFactor=64;d.tessellationFactorFormat=MTLTessellationFactorFormatHalf;d.tessellationControlPointIndexType=MTLTessellationControlPointIndexTypeNone;d.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionPerPatchAndPerInstance;d.tessellationOutputWindingOrder=MTLWindingCounterClockwise;
        NSError *e=nil;raster=[g_dev newRenderPipelineStateWithDescriptor:d error:&e];if(!raster)MDIE("TES/fragment pipeline %s/%s: %s",te->key,fs?fs->key:"none",e.description.UTF8String);hm_put_id(&render_cache,&rkey,raster);}
    // CPU lifetime is bounded by completion of the ordered island. No guest
    // indices, factors or vertex results are read back or replaced on the CPU.
    id<MTLBuffer> vertices=[g_dev newBufferWithLength:(NSUInteger)count*instances*TITLE_TESS_POINT_BYTES options:MTLResourceStorageModePrivate];
    id<MTLBuffer> controls=[g_dev newBufferWithLength:(NSUInteger)total*3*TITLE_TESS_POINT_BYTES options:MTLResourceStorageModePrivate];
    uint64_t factor_base=(uint64_t)patches*base;
    if(factor_base+total>3*1048576)MDIE("Tessellation factor base-instance extent too large");
    id<MTLBuffer> factors=[g_dev newBufferWithLength:(NSUInteger)(factor_base+total)*sizeof(MTLTriangleTessellationFactorsHalf) options:MTLResourceStorageModePrivate];
    if(!vertices||!controls||!factors)MDIE("Tessellation transient allocation");
    uint32_t params[5]={3,total,patches,base,dw?(uint32_t)dw->first:0};id<MTLBuffer> index32=nil;
    id<MTLCommandBuffer> cb=[g_q commandBuffer];cb.label=@"Original VS/TCS + Metal tessellator + original TES";
#if !DM_NVN_M3
    static id<MTLSharedEvent> bridge;static uint64_t tick;if(!bridge)bridge=[g_dev newSharedEvent];uint64_t ready=++tick,done=++tick;
    [cb encodeWaitForEvent:bridge value:ready];
#endif
    // GPU widening retains the original 16/32-bit index sequence.
    if(di){if(di->itype!=1&&di->itype!=2)MDIE("Unsupported tessellation index type %d",di->itype);
        void *buffer;uint64_t off;if(!mtl_addr(di->ibuf,(uint64_t)count*(di->itype==1?2:4),&buffer,&off))MDIE("Tessellation indices outside memory pool");
        if(di->itype==2){index32=(__bridge id<MTLBuffer>)buffer;}
        else {static id<MTLComputePipelineState> widen;NSError *e=nil;if(!widen){id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;kernel void widen(device const ushort*i[[buffer(0)]],device uint*o[[buffer(1)]],uint x[[thread_position_in_grid]]){o[x]=i[x];}" options:nil error:&e];widen=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"widen"] error:&e];if(!widen)MDIE("Index widening kernel %s",e.description.UTF8String);}
            index32=[g_dev newBufferWithLength:count*4 options:MTLResourceStorageModePrivate];id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];[ce setComputePipelineState:widen];[ce setBuffer:(__bridge id<MTLBuffer>)buffer offset:off atIndex:0];[ce setBuffer:index32 offset:0 atIndex:1];[ce dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[ce endEncoding];}
    }
    id<MTLComputeCommandEncoder> ve=[cb computeCommandEncoder];[ve setComputePipelineState:title_tess_vertex_pipeline(vs,di!=NULL)];
    if(di){void *b;uint64_t off;mtl_addr(di->ibuf,1,&b,&off);[ve setBuffer:index32 offset:di->itype==2?off:0 atIndex:1];}
    for(int i=0;i<14;i++)if(S.vbuf[i].address){int64_t adjust=di&&!S.stream[i].divisor?(int64_t)di->base_vertex*S.stream[i].stride:0;void *b;uint64_t off;
        if(!mtl_addr(S.vbuf[i].address+adjust,1,&b,&off))MDIE("Tessellation vertex buffer outside memory pool");[ve setBuffer:(__bridge id<MTLBuffer>)b offset:off atIndex:16+i];}
    [ve setBuffer:vertices offset:0 atIndex:2];[ve setBytes:params length:sizeof params atIndex:3];g_tess_binding=1;args_dirty_all();encode_args(ve,vs,0,0);
    [ve setStageInRegion:MTLRegionMake2D(dw?dw->first:0,base,count,instances)];[ve dispatchThreads:MTLSizeMake(count,instances,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[ve endEncoding];
    id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];[ce setComputePipelineState:title_tess_control_pipeline(tc)];args_dirty_all();encode_args(ce,tc,3,0);[ce setBuffer:vertices offset:0 atIndex:1];[ce setBuffer:controls offset:0 atIndex:2];[ce setBytes:params length:sizeof params atIndex:3];[ce setBuffer:factors offset:factor_base*sizeof(MTLTriangleTessellationFactorsHalf) atIndex:4];[ce dispatchThreads:MTLSizeMake(total*3,1,1) threadsPerThreadgroup:MTLSizeMake(96,1,1)];[ce endEncoding];
    id<MTLBuffer> trace=nil;
    static unsigned traced;
    if(getenv("DM_TESS_TRACE")&&traced++<3){trace=[g_dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];[bl copyFromBuffer:vertices sourceOffset:0 toBuffer:trace destinationOffset:0 size:3*TITLE_TESS_POINT_BYTES];[bl copyFromBuffer:controls sourceOffset:0 toBuffer:trace destinationOffset:1600 size:3*TITLE_TESS_POINT_BYTES];[bl copyFromBuffer:factors sourceOffset:factor_base*8 toBuffer:trace destinationOffset:3200 size:MIN(total,3u)*8];[bl endEncoding];}
    id<MTLBuffer> visibility=nil;if(g_vis_counting){visibility=[g_dev newBufferWithLength:8 options:MTLResourceStorageModeShared];pass.visibilityResultBuffer=visibility;}
    id<MTLRenderCommandEncoder> re=[cb renderCommandEncoderWithDescriptor:pass];[re setRenderPipelineState:raster];[re setDepthStencilState:dss_get(df!=0,sf!=0)];[re setStencilFrontReferenceValue:S.st_ref[0] backReferenceValue:S.st_ref[1]];
    [re setViewport:S.has_vp?(MTLViewport){S.vp[0][0],S.vp[0][1],S.vp[0][2],S.vp[0][3],S.dr[0],S.dr[1]}:(MTLViewport){0,0,width,height,S.dr[0],S.dr[1]}];
    if(R.has_sc)[re setScissorRect:scissor];
    [re setCullMode:S.poly.cull==NVN_FACE_FRONT?MTLCullModeFront:S.poly.cull==NVN_FACE_BACK?MTLCullModeBack:MTLCullModeNone];
    if(S.poly.cull==NVN_FACE_FRONT_AND_BACK)MDIE("Tessellation front-and-back culling needs an explicit empty-draw path");
    [re setFrontFacingWinding:S.poly.front==NVN_FRONT_FACE_CCW?MTLWindingCounterClockwise:MTLWindingClockwise];[re setTriangleFillMode:S.poly.mode==NVN_POLYGON_MODE_LINE?MTLTriangleFillModeLines:MTLTriangleFillModeFill];
    [re setDepthClipMode:S.depth_clamp?MTLDepthClipModeClamp:MTLDepthClipModeClip];if(S.poly.offset_en&4)[re setDepthBias:S.po.units slopeScale:S.po.factor clamp:S.po.clamp];[re setBlendColorRed:S.blend_color[0] green:S.blend_color[1] blue:S.blend_color[2] alpha:S.blend_color[3]];
    g_tess_binding=2;args_dirty_all();encode_args(re,te,4,1);[re setVertexBuffer:controls offset:0 atIndex:1];[re setVertexBytes:params length:sizeof params atIndex:3];
    g_tess_binding=3;if(fs){args_dirty_all();encode_args(re,fs,1,0);}
    float range[4]={S.depth_bounds.enabled&&R.rt.depth,S.depth_bounds.min,S.depth_bounds.max,0};[re setFragmentBytes:range length:sizeof range atIndex:26];id<MTLTexture> depth_image=range[0]?g_depth_bounds_image:dummy_tex(MTLTextureType2D,0);[re setFragmentTexture:depth_image atIndex:0];[re useResource:depth_image usage:MTLResourceUsageRead stages:MTLRenderStageFragment];
    uint32_t alpha[2]={S.color.alpha_func,0};memcpy(alpha+1,&S.alpha_ref,4);[re setFragmentBytes:alpha length:sizeof alpha atIndex:27];
    [re setTessellationFactorBuffer:factors offset:0 instanceStride:patches*sizeof(MTLTriangleTessellationFactorsHalf)];if(visibility)[re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
    id<MTLBuffer> probe=nil;if(trace){probe=[g_dev newBufferWithLength:8192 options:MTLResourceStorageModeShared];((uint32_t *)probe.contents)[1]=UINT32_MAX;[re setVertexBuffer:probe offset:0 atIndex:5];}
    [re drawPatches:3 patchStart:0 patchCount:patches patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:instances baseInstance:base];[re endEncoding];g_tess_binding=0;
    id<MTLBuffer> trace_color=nil;
    if(trace && pass.colorAttachments[0].texture.pixelFormat==MTLPixelFormatRGBA32Float){trace_color=[g_dev newBufferWithLength:width*height*16 options:MTLResourceStorageModeShared];id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];[bl copyFromTexture:pass.colorAttachments[0].texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(width,height,1) toBuffer:trace_color destinationOffset:0 destinationBytesPerRow:width*16 destinationBytesPerImage:width*height*16];[bl endEncoding];}
#if !DM_NVN_M3
    [cb encodeSignalEvent:bridge value:done];
#endif
    uint64_t fence=mtl_sub_commit();
#if !DM_NVN_M3
    [g_q4 signalEvent:bridge value:ready];
#endif
    if(!mtl_wait(fence,10000000000ull)||mtl_last_commit_error())MDIE("Tessellation preceding Metal 4 submission failed");
    gpu_tag(cb);[cb commit];
#if !DM_NVN_M3
    [g_q4 waitForEvent:bridge value:done];
#endif
    [cb waitUntilCompleted];if(cb.error)MDIE("Tessellation GPU failure: %s",cb.error.description.UTF8String);
    if(trace_color){unsigned red=0;const float*p=trace_color.contents;for(NSUInteger i=0;i<width*height;i++)red+=p[i*4]>.9;MLOG("[tess-trace] legacy output red pixels=%u",red);}
    if(probe){const uint32_t*p=probe.contents;MLOG("[tess-trace] TES invocations=%u instance=%u..%u patch=%u",p[0],p[1],p[2],p[3]);const float*v=(const float*)(p+4);for(int i=0;i<MIN(p[0],8u);i++)MLOG("[tess-trace] TES output%d=%g,%g,%g,%g",i,v[4*i],v[4*i+1],v[4*i+2],v[4*i+3]);}
    if(trace){const float *v=trace.contents,*c=(const float *)((const uint8_t *)trace.contents+1600);const __fp16*f=(const __fp16 *)((const uint8_t*)trace.contents+3200);
        for(int i=0;i<3;i++)MLOG("[tess-trace] v%d=%g,%g,%g,%g tc=%g,%g,%g,%g",i,v[i*132+128],v[i*132+129],v[i*132+130],v[i*132+131],c[i*132+128],c[i*132+129],c[i*132+130],c[i*132+131]);MLOG("[tess-trace] factors=%g,%g,%g inside=%g",(double)f[0],(double)f[1],(double)f[2],(double)f[3]);}
    if(visibility){if(g_nvs==g_vscap){g_vscap=g_vscap?g_vscap*2:64;g_vs=realloc(g_vs,g_vscap*sizeof *g_vs);}g_vs[g_nvs++]=(vis_slot){(void *)CFBridgingRetain(visibility),0};}
    static uint64_t draws,reported=~0ull;draws++;uint64_t frame=atomic_load(&g_cur_frame);
    if(draws==1||(!(frame%300)&&reported!=frame)){reported=frame;MLOG("[tessellation] frame=%llu draws=%llu patches=%u instances=%d VS=%s TCS=%s TES=%s GPU=%.3fms",(unsigned long long)frame,(unsigned long long)draws,patches,instances,vs->key,tc->key,te->key,(cb.GPUEndTime-cb.GPUStartTime)*1000);}
    g_stat_draw++;g_stat_pass++;
    uint64_t old_id=pass.colorAttachments[0].texture.gpuResourceID._impl;
    mtl_sub_begin();args_dirty_all();g_pso_dirty=g_dss_dirty=1;
#if !DM_NVN_M3
    BENC barrier=enc_b_begin(g_cb);[barrier barrierAfterQueueStages:MTLStageAll beforeStages:MTLStageAll visibilityOptions:MTL4VisibilityOptionDevice];enc_b_end(barrier);
#endif
    if(trace && R.rt.color[0])MLOG("[tess-trace] color resource before=%llu after=%llu clear=%d",(unsigned long long)old_id,(unsigned long long)tex_mtl(R.rt.color[0]).gpuResourceID._impl,R.clear_c[0]);
}
