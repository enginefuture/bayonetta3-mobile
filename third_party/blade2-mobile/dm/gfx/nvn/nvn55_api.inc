// Targeted NVN 55.12 adapters. SDK function ABI/record layouts are recorded in
// work/analysis; deferred references are materialized only by QueueSubmitCommands.
#if DM_BAYONETTA3
static void nvn55_multi_draw(NVNcommandBuffer *c,int primitive,int type,uint64_t indices,uint64_t args,uint64_t count,int maximum,ptrdiff_t stride){
    int bytes=type<0?16:20;
    if(maximum<0 || maximum>65535 || (type!=-1 && type!=1 && type!=2) || stride<0 || stride>INT32_MAX || (stride && (stride<bytes || (stride&3))) || (maximum && (!args || !count || (args&3) || (count&3))))die("invalid MultiDrawIndirectCount parameters");
    if(maximum)*REC(c,OP_MULTI_DRAW,p_multi_draw)=(p_multi_draw){primitive,type,maximum,stride?(int)stride:bytes,indices,args,count};
}
NVN(nvnCommandBufferMultiDrawArraysIndirectCount,void,NVNcommandBuffer *c,NVNdrawPrimitive primitive,NVNbufferAddress args,NVNbufferAddress count,int maximum,ptrdiff_t stride){
    nvn55_multi_draw(c,primitive,-1,0,args,count,maximum,stride);
}
NVN(nvnCommandBufferMultiDrawElementsIndirectCount,void,NVNcommandBuffer *c,NVNdrawPrimitive primitive,NVNindexType type,NVNbufferAddress indices,NVNbufferAddress args,NVNbufferAddress count,int maximum,ptrdiff_t stride){
    nvn55_multi_draw(c,primitive,type,indices,args,count,maximum,stride);
}
NVN(nvnCommandBufferDispatchComputeIndirect,void,NVNcommandBuffer *c,NVNbufferAddress args){
    if(!args || (args&3))die("DispatchComputeIndirect invalid argument address");
    *REC(c,OP_DISPATCH,p_dispatch)=(p_dispatch){.caller=(uint64_t)__builtin_return_address(0),.indirect=args};
}
NVN(nvnCommandBufferSetDepthBounds,void,NVNcommandBuffer *c,uint32_t enabled,float near,float far){
    if(!isfinite(near) || !isfinite(far))die("nonfinite depth bounds");
    *REC(c,OP_DEPTH_BOUNDS,p_depth_bounds)=(p_depth_bounds){B(enabled)!=0,near,far,0};
}
NVN(nvnCommandBufferSetShaderScratchMemory,void,NVNcommandBuffer *c,const NVNmemoryPool *p,ptrdiff_t offset,size_t size){
    const pool_t *pool=(const pool_t *)p;
    if(offset<0 || (size && (!pool || size>pool->size || (uint64_t)offset>pool->size-size)))die("shader scratch range outside memory pool");
    // Maxwell scratch backing is a driver allocation hint. Metal allocates
    // private per-thread shader storage from the compiled pipeline itself.
    uint32_t *record=(uint32_t *)(cmd_alloc(CB(c),24)+8);record[0]=3;record[1]=record[2]=record[3]=0;put_hdr((uint8_t *)record-8,OP_BACKEND_HINT,24);
    static int once;if(!once++)LOG("[nvn55] Metal manages shader scratch backing (NVN request %zu bytes)",size);
}
// Metal owns hierarchical depth metadata; no application ZCull backing allocation.
NVN(nvnTextureBuilderGetZCullStorageSize,size_t,const NVNtextureBuilder *b){(void)b;return 0;}
NVN(nvnTextureGetZCullStorageSize,size_t,const NVNtexture *t){(void)t;return 0;}
NVN(nvnBufferFlushMappedRange,void,const NVNbuffer *b,ptrdiff_t off,size_t n){
    const buf_t *o=(const buf_t *)b;
    if(off<0 || n>o->size || (uint64_t)off>o->size-n)die("BufferFlushMappedRange outside buffer");
    atomic_thread_fence(memory_order_release); // MTLStorageModeShared on Apple silicon.
}
NVN(nvnBufferInvalidateMappedRange,void,const NVNbuffer *b,ptrdiff_t off,size_t n){
    const buf_t *o=(const buf_t *)b;
    if(off<0 || n>o->size || (uint64_t)off>o->size-n)die("BufferInvalidateMappedRange outside buffer");
    atomic_thread_fence(memory_order_acquire);
}
NVN(nvnMemoryPoolGetFlags,NVNmemoryPoolFlags,const NVNmemoryPool *p){return (NVNmemoryPoolFlags)((const pool_t *)p)->flags;}
NVN(nvnSamplerBuilderGetLodClamp,void,const NVNsamplerBuilder *b,float *min,float *max){*min=SB(b)->lod_min;*max=SB(b)->lod_max;}
NVN(nvnSamplerBuilderGetLodBias,float,const NVNsamplerBuilder *b){return SB(b)->lod_bias;}
NVN(nvnSamplerBuilderGetMaxAnisotropy,float,const NVNsamplerBuilder *b){return SB(b)->aniso;}
NVN(nvnSamplerBuilderGetCompare,void,const NVNsamplerBuilder *b,NVNcompareMode *mode,NVNcompareFunc *func){*mode=(NVNcompareMode)SB(b)->cmp_mode;*func=(NVNcompareFunc)SB(b)->cmp_func;}
NVN(nvnSamplerBuilderGetBorderColor,void,const NVNsamplerBuilder *b,float *out){memcpy(out,SB(b)->border,16);}
NVN(nvnSamplerBuilderGetBorderColori,void,const NVNsamplerBuilder *b,int *out){memcpy(out,SB(b)->border,16);}
NVN(nvnSamplerBuilderGetBorderColorui,void,const NVNsamplerBuilder *b,uint32_t *out){memcpy(out,SB(b)->border,16);}
NVN(nvnTextureGetMemoryPool,NVNmemoryPool *,const NVNtexture *t){return (NVNmemoryPool *)CTX(t)->pool;}
NVN(nvnTextureGetMemoryOffset,ptrdiff_t,const NVNtexture *t){return CTX(t)->off;}
NVN(nvnTextureGetFormat,NVNformat,const NVNtexture *t){return (NVNformat)CTX(t)->d.format;}
NVN(nvnBufferGetMemoryPool,NVNmemoryPool *,const NVNbuffer *b){return (NVNmemoryPool *)((const buf_t *)b)->pool;}
NVN(nvnBufferGetMemoryOffset,ptrdiff_t,const NVNbuffer *b){return ((const buf_t *)b)->off;}
NVN(nvnBufferGetSize,size_t,const NVNbuffer *b){return ((const buf_t *)b)->size;}
NVN(nvnMemoryPoolGetSize,size_t,const NVNmemoryPool *p){return ((const pool_t *)p)->size;}
static void nvn55_swizzle(uint8_t *out,int r,int g,int b,int a){
    if((unsigned)r>5 || (unsigned)g>5 || (unsigned)b>5 || (unsigned)a>5)die("invalid texture swizzle");
    out[0]=r;out[1]=g;out[2]=b;out[3]=a;
}
static void nvn55_get_swizzle(const uint8_t *s,NVNtextureSwizzle *r,NVNtextureSwizzle *g,NVNtextureSwizzle *b,NVNtextureSwizzle *a){
    *r=(NVNtextureSwizzle)s[0];*g=(NVNtextureSwizzle)s[1];*b=(NVNtextureSwizzle)s[2];*a=(NVNtextureSwizzle)s[3];
}
static const uint8_t nvn55_rgba[4]={2,3,4,5};
NVN(nvnTextureBuilderSetSwizzle,void,NVNtextureBuilder *b,NVNtextureSwizzle r,NVNtextureSwizzle g,NVNtextureSwizzle blue,NVNtextureSwizzle a){
    nvn55_swizzle(TB(b)->d.swizzle,r,g,blue,a);TB(b)->d.has_swizzle=1;
}
NVN(nvnTextureBuilderGetSwizzle,void,const NVNtextureBuilder *b,NVNtextureSwizzle *r,NVNtextureSwizzle *g,NVNtextureSwizzle *blue,NVNtextureSwizzle *a){const nvn_texdesc *d=&((const tex_builder_t *)b)->d;nvn55_get_swizzle(d->has_swizzle?d->swizzle:nvn55_rgba,r,g,blue,a);}
NVN(nvnTextureGetSwizzle,void,const NVNtexture *t,NVNtextureSwizzle *r,NVNtextureSwizzle *g,NVNtextureSwizzle *b,NVNtextureSwizzle *a){const nvn_texdesc *d=&CTX(t)->d;nvn55_get_swizzle(d->has_swizzle?d->swizzle:nvn55_rgba,r,g,b,a);}
NVN(nvnTextureViewSetSwizzle,void,NVNtextureView *v,NVNtextureSwizzle r,NVNtextureSwizzle g,NVNtextureSwizzle b,NVNtextureSwizzle a){view_t o=nvn_view_decode(v);nvn55_swizzle(o.swizzle,r,g,b,a);o.set_swizzle=1;nvn_view_encode(v,&o);}
NVN(nvnTextureViewGetSwizzle,NVNboolean,const NVNtextureView *v,NVNtextureSwizzle *r,NVNtextureSwizzle *g,NVNtextureSwizzle *b,NVNtextureSwizzle *a){view_t o=nvn_view_decode(v);nvn55_get_swizzle(o.swizzle,r,g,b,a);return o.set_swizzle;}
#include "nvn55_texels.h"
static void nvn55_write_texels(const NVNtexture *t,const NVNtextureView *view,const NVNcopyRegion *r,const void *src,ptrdiff_t row,ptrdiff_t img){
    const tex_t *o=CTX(t);view_t decoded=nvn_view_decode(view);const view_t *v=view?&decoded:NULL;
    unsigned lv=v && v->set_levels?v->base_level:0,layer=v && v->set_layers?v->min_layer:0;
    if(row<0 || img<0)die("TextureWriteTexels negative stride unsupported");
    if(!nvn55_write_storage(o,lv,layer,r,src,row,img))die("TextureWriteTexels invalid/unsupported region");
    mtl_write_texels(o,lv,layer,r,src,row,img);
}
NVN(nvnTextureWriteTexels,void,const NVNtexture *t,const NVNtextureView *v,const NVNcopyRegion *r,const void *src){nvn55_write_texels(t,v,r,src,0,0);}
NVN(nvnTextureWriteTexelsStrided,void,const NVNtexture *t,const NVNtextureView *v,const NVNcopyRegion *r,const void *src,ptrdiff_t row,ptrdiff_t img){nvn55_write_texels(t,v,r,src,row,img);}
NVN(nvnTextureViewSetDepthStencilMode,void,NVNtextureView *v,NVNtextureDepthStencilMode mode){if((unsigned)mode>1)die("invalid depth/stencil mode");view_t o=nvn_view_decode(v);o.set_ds_mode=1;o.ds_mode=mode;nvn_view_encode(v,&o);}
NVN(nvnTextureViewGetDepthStencilMode,NVNboolean,const NVNtextureView *v,NVNtextureDepthStencilMode *mode){view_t o=nvn_view_decode(v);*mode=(NVNtextureDepthStencilMode)o.ds_mode;return o.set_ds_mode;}
NVN(nvnTextureBuilderGetDepthStencilMode,NVNtextureDepthStencilMode,const NVNtextureBuilder *b){return (NVNtextureDepthStencilMode)((const tex_builder_t *)b)->d.ds_mode;}
NVN(nvnTextureGetDepthStencilMode,NVNtextureDepthStencilMode,const NVNtexture *t){return (NVNtextureDepthStencilMode)CTX(t)->d.ds_mode;}
NVN(nvnColorStateSetAlphaTest,void,NVNcolorState *st,NVNalphaFunc f){if(f<1 || f>8)die("invalid alpha test function");ST(color_st,st)->alpha_func=f;}
NVN(nvnColorStateGetAlphaTest,NVNalphaFunc,const NVNcolorState *st){return (NVNalphaFunc)((const color_st *)st)->alpha_func;}
NVN(nvnColorStateSetLogicOp,void,NVNcolorState *st,NVNlogicOp op){ST(color_st,st)->logic_op=op;}
NVN(nvnColorStateGetLogicOp,NVNlogicOp,const NVNcolorState *st){return (NVNlogicOp)((const color_st *)st)->logic_op;}
NVN(nvnColorStateGetBlendEnable,NVNboolean,const NVNcolorState *st,int i){if(i<0 || i>7)die("invalid blend target");return (((const color_st *)st)->blend_en>>i)&1;}
NVN(nvnCommandBufferSetAlphaRef,void,NVNcommandBuffer *c,float value){uint8_t *p=cmd_alloc(CB(c),16);put_hdr(p,OP_ALPHA_REF,16);memcpy(p+8,&value,4);}
NVN(nvnCommandBufferClearBuffer,void,NVNcommandBuffer *c,NVNbufferAddress a,size_t n,uint32_t value){
    if((a&3) || (n&3))die("ClearBuffer requires 4-byte aligned address/size");
    *REC(c,OP_CLEAR_BUFFER,p_clear_buffer)=(p_clear_buffer){a,n,value,0};
}
NVN(nvnCommandBufferSetLineWidth,void,NVNcommandBuffer *c,float width){(void)c;if(width!=1.0f)die("Metal supports only unit-width native lines (requested %g)",(double)width);}
NVN(nvnCommandBufferSetColorReductionEnable,void,NVNcommandBuffer *c,uint32_t enabled){(void)c;if(B(enabled))die("Metal lossy color reduction requested but unsupported");}
NVN(nvnCommandBufferSetColorReductionThresholds,void,NVNcommandBuffer *c,int format_class,int a,int b){
    if((unsigned)format_class>5)return;int max=format_class==3?63:255;
    uint8_t *r=cmd_alloc(CB(c),32);put_hdr(r,OP_BACKEND_HINT,32);uint32_t *p=(uint32_t *)(r+8);
    p[0]=3;p[1]=format_class;p[2]=a<0?0:a>max?max:a;p[3]=b<0?0:b>max?max:b;p[4]=p[5]=0;
    // Reduction enable=true is rejected; thresholds have no effect when disabled.
}
NVN(nvnVertexStreamStateGetStride,ptrdiff_t,const NVNvertexStreamState *s){return ((const vs_st *)s)->stride;}
NVN(nvnVertexStreamStateGetDivisor,int,const NVNvertexStreamState *s){return ((const vs_st *)s)->divisor;}
NVN(nvnVertexAttribStateGetFormat,void,const NVNvertexAttribState *s,NVNformat *format,ptrdiff_t *offset){*format=(NVNformat)((const va_st *)s)->fmt;*offset=((const va_st *)s)->offset;}
NVN(nvnVertexAttribStateGetStreamIndex,int,const NVNvertexAttribState *s){return ((const va_st *)s)->stream;}
NVN(nvnCommandBufferSetDepthClamp,void,NVNcommandBuffer *c,uint32_t enabled){uint8_t *p=cmd_alloc(CB(c),16);put_hdr(p,OP_DEPTH_CLAMP,16);uint32_t value=B(enabled)!=0;memcpy(p+8,&value,4);}
NVN(nvnCommandBufferBindTextures,void,NVNcommandBuffer *c,NVNshaderStage stage,int first,int n,const NVNtextureHandle *handles){
 if(stage<0 || stage>=6 || first<0 || n<0 || first>128 || n>128-first || (n && !handles))die("BindTextures invalid range");
 for(int i=0;i<n;){int k=n-i;if(k>32)k=32;uint64_t samplers[32];for(int j=0;j<k;j++)samplers[j]=handles[i+j]&~0xFFFFFull;
 bind_handles(c,OP_BIND_TEX,stage,first+i,k,(const uint64_t *)handles+i);bind_handles(c,OP_BIND_SAMP,stage,first+i,k,samplers);i+=k;}
}
NVN(nvnCommandBufferSaveZCullData,void,NVNcommandBuffer *c,NVNbufferAddress address,size_t size){(void)c;(void)address;if(size)die("nonempty Maxwell ZCull metadata save unsupported");}
NVN(nvnCommandBufferRestoreZCullData,void,NVNcommandBuffer *c,NVNbufferAddress address,size_t size){(void)c;(void)address;if(size)die("nonempty Maxwell ZCull metadata restore unsupported");}
NVN(nvnWindowGetCrop,void,const NVNwindow *w,NVNrectangle *out){if(!out)die("WindowGetCrop null output");memcpy(out,((const win_t *)w)->crop,16);}
NVN(nvnCommandBufferDrawElementsIndirect,void,NVNcommandBuffer *c,NVNdrawPrimitive primitive,NVNindexType type,NVNbufferAddress indices,NVNbufferAddress args){
 if(!args || (args&3) || type<1 || type>2)die("DrawElementsIndirect invalid index/argument format");
 *REC(c,OP_DRAW_IDX,p_draw_idx)=(p_draw_idx){.prim=primitive,.itype=type,.ibuf=indices,.indirect=args};
}
NVN(nvnCommandBufferDrawArraysIndirect,void,NVNcommandBuffer *c,NVNdrawPrimitive primitive,NVNbufferAddress args){
 if(!args || (args&3))die("DrawArraysIndirect invalid arguments");*REC(c,OP_DRAW,p_draw)=(p_draw){.prim=primitive,.indirect=args};
}
static void nvn55_defer(NVNcommandBuffer *c,int op,int stage,int first,int n,const void *source) {
    int limit=(op==OP_BIND_UBO || op==OP_BIND_SSBO)?16:op==OP_BIND_IMG?32:128;
    if(stage<0 || stage>=6 || first<0 || n<0 || first>limit || n>limit-first || (n && (!source || ((uintptr_t)source&7))))
        die("NVN deferred binding invalid op=%d stage=%d first=%d n=%d",op,stage,first,n);
    if(n)*REC(c,OP_BIND_DEFERRED,p_bind_deferred)=(p_bind_deferred){op,stage,first,n,(uintptr_t)source};
}
NVN(nvnCommandBufferBindUniformBuffersDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNbufferRange *v){nvn55_defer(c,OP_BIND_UBO,s,first,n,v);}
NVN(nvnCommandBufferBindStorageBuffersDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNbufferRange *v){nvn55_defer(c,OP_BIND_SSBO,s,first,n,v);}
NVN(nvnCommandBufferBindTexturesDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNtextureHandle *v){nvn55_defer(c,OP_BIND_COMBINED,s,first,n,v);}
NVN(nvnCommandBufferBindImagesDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNimageHandle *v){nvn55_defer(c,OP_BIND_IMG,s,first,n,v);}
NVN(nvnCommandBufferBindSeparateTexturesDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNseparateTextureHandle *v){nvn55_defer(c,OP_BIND_TEX,s,first,n,v);}
NVN(nvnCommandBufferBindSeparateSamplersDeferred,void,NVNcommandBuffer *c,NVNshaderStage s,int first,int n,const NVNseparateSamplerHandle *v){nvn55_defer(c,OP_BIND_SAMP,s,first,n,v);}
NVN(nvnTextureBuilderGetViewOffset,ptrdiff_t,const NVNtextureBuilder *b,const NVNtextureView *view){
    const tex_builder_t *t=(const tex_builder_t *)b;view_t decoded=nvn_view_decode(view);const view_t *v=view?&decoded:NULL;
    if(!v)return 0;
    if((v->set_levels && (v->base_level<0 || (unsigned)v->base_level>=t->d.levels)) || (v->set_layers && v->min_layer<0))die("TextureBuilderGetViewOffset invalid view");
    nvn_texlayout layout;nvn_tex_layout(&t->d,&layout);
    return (ptrdiff_t)((v->set_levels?nvn_tex_level_offset(&t->d,v->base_level):0)+(v->set_layers?(uint64_t)v->min_layer*layout.layer_size:0));
}
NVN(nvnProgramGetSubtileSize,int,const NVNprogram *p){
    const prog_t *v=(const prog_t *)p;if(v->magic!=MAGIC('P','R','O','G'))die("ProgramGetSubtileSize invalid program");
    // No Maxwell-specific subtile override on Metal: automatic backend scheduling.
    return (int)v->subtile;
}
NVN(nvnDeviceSetAutomaticCheckpointsMask,NVNboolean,NVNdevice *d,int mask){
    (void)d;(void)mask;return 1; // Supplied release SDK implementation is mov w0,#1;ret.
}
NVN(nvnCommandBufferOverrideSubtileSize,void,NVNcommandBuffer *c,uint32_t enabled,int size){
    uint32_t *p=(uint32_t *)(cmd_alloc(CB(c),24)+8);p[0]=1;p[1]=B(enabled)!=0;p[2]=(uint32_t)(size<1?1:size>128?128:size);p[3]=0;
    put_hdr((uint8_t *)p-8,OP_BACKEND_HINT,24);
}
NVN(nvnCommandBufferSetZCullZF32CompressionEnable,void,NVNcommandBuffer *c,uint32_t enabled){
    uint32_t *p=(uint32_t *)(cmd_alloc(CB(c),24)+8);p[0]=2;p[1]=enabled&1;p[2]=p[3]=0;
    put_hdr((uint8_t *)p-8,OP_BACKEND_HINT,24);
}
#endif
