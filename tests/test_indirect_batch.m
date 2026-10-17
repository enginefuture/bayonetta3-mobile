#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_mtl.m"
void *front_metal_layer(void){return NULL;}
module_t *module_of(const void *p){(void)p;return NULL;}
module_t g_mod[MAX_MOD];int g_nmod;
uint64_t g_t0_ns;
void svc_thread_dump(void){}
uint64_t now_ns(void){return bp_now();}
uint64_t nvn_new_serial(void){static uint64_t s=100000;return ++s;}
typedef struct{uint8_t bytes[8192];size_t n;} commands;
static const void *emit(commands *c,int op,const void *p,size_t n){
    size_t z=(8+n+7)&~7ull;assert(c->n+z<=sizeof c->bytes);op_hdr h={op,(uint32_t)z};
    uint8_t *a=c->bytes+c->n;memcpy(a,&h,8);if(n)memcpy(a+8,p,n);c->n+=z;return a+8;
}
int main(void){@autoreleasepool{
    setenv("DM_NVN_INDIRECT_BATCH","1",1);mtl_init();
    assert(rt_range_bindings_ro(@{@"route":@"B",@"drv_reads":@{},@"bindings":@[@{@"kind":@"support",@"msl_type":@"constant Helper*"},@{@"kind":@"samp_tex",@"msl_type":@"sampler"}]}));
    assert(!rt_range_bindings_ro(@{@"route":@"B",@"drv_reads":@{},@"bindings":@[@{@"kind":@"support",@"msl_type":@"device Helper*"}]}));
    prog_t program={.serial=99001};NvProg *pr=[NvProg new];
    for(int k=0;k<2;k++){pr->sh[k]=[NvShader new];pr->sh[k]->stage=k;pr->sh[k]->range_ro=1;}
    serial_put(program.serial,pr);S.prog=&program;R.has_rt=1;
    pr->sh[5]=[NvShader new];pr->sh[5]->stage=5;pr->sh[5]->range_ro=0;
    assert(rt_range_pr_ro(pr)); // Independently bound compute is not executed by a draw.
    void *memory;assert(!posix_memalign(&memory,getpagesize(),getpagesize()));memset(memory,0,getpagesize());mtl_pool_add(memory,getpagesize());
    uint32_t *source=memory,*counts=source+512;
    for(int i=0;i<96;i++)source[i]=i+100;source[3]=(uint32_t)-7;
    for(int i=0;i<8;i++)counts[i]=0xdeadbeef;
    p_multi_draw p[8];commands code={0};const p_multi_draw *payload[8];
    for(int i=0;i<8;i++){
        p[i]=(p_multi_draw){.type=i%2?-1:1,.maximum=3,.stride=28,.args=(uintptr_t)(source+i*7),.count=(uintptr_t)(counts+i)};
        payload[i]=emit(&code,OP_MULTI_DRAW,&p[i],sizeof p[i]);
    }
    emit(&code,OP_END,NULL,0);
    const uint8_t *next=(const uint8_t *)payload[1]-8;
    // A private scanner must not leak speculative bindings/scissors into replay.
    assert(title_batch_collect(payload[0],next)==8 && S.prog==&program && !R.has_sc);
    commands blocked={0};emit(&blocked,OP_UPDATE_UB,NULL,0);emit(&blocked,OP_MULTI_DRAW,&p[1],sizeof p[1]);emit(&blocked,OP_END,NULL,0);
    assert(!title_batch_collect(payload[0],blocked.bytes));
    pr->sh[1]->range_ro=0;assert(!title_batch_collect(payload[0],next));pr->sh[1]->range_ro=1;
    tex_t alias={.mem=(uint8_t *)source,.L.size=256};R.rt.n=1;R.rt.color[0]=&alias;
    assert(!title_batch_collect(payload[0],next));R.rt.n=0;R.rt.color[0]=NULL;
    assert(title_ranges_overlap(UINT64_MAX-1,4,1,4));
    // Alias guards resolve the active descriptor namespace and stage override.
    tex_t target={.serial=99010,.mem=(uint8_t *)memory,.L.size=256};
    tex_t sampled={.serial=99011,.mem=(uint8_t *)memory+128,.L.size=128};
    R.rt.n=1;R.rt.color[0]=&target;g_active_tbase=100;g_active_tcount=2;
    mtl_reg_tex(101,&sampled,NULL);pr->sh[1]->rf.nb=1;pr->sh[1]->rf.b[0]=(nvn_rbind){.kind=NVN_RB_TEX,.reg=0,.st=2};S.tex[2][0]=1;
    assert(draw_samples_rt(pr));
    sampled.mem=(uint8_t *)memory+512;mtl_reg_tex(101,&sampled,NULL);assert(!draw_samples_rt(pr));
    pr->sh[1]->rf.nb=0;g_active_tbase=g_active_tcount=0;R.rt.n=0;R.rt.color[0]=NULL;
    // GPU writes the counts AFTER CPU command recording. Reading them on CPU
    // would give deadbeef and fail the zero/one cases below.
    mtl_sub_begin();NSError *error=nil;
    id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;kernel void seed(device uint* c[[buffer(0)]],uint i[[thread_position_in_grid]]){if(i<8)c[i]=(i%4==0?0:i%4==1?1:i%4==2?3:99);}" options:nil error:&error];assert(lib);
    id<MTLComputePipelineState> ps=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"seed"] error:&error];assert(ps);
    void *cb;uint64_t co,cg;assert(mtl_gpu_addr((uintptr_t)counts,32,&cb,&co,&cg));
    MTL4ArgumentTableDescriptor *td=[MTL4ArgumentTableDescriptor new];td.maxBufferBindCount=1;
    id<MTL4ArgumentTable> table=[g_dev newArgumentTableWithDescriptor:td error:&error];assert(table);[table setAddress:cg atIndex:0];
    CENC ce=enc_c_begin(NULL);[ce setArgumentTable:table];enc_c_pso(ce,ps);enc_c_dispatch(ce,MTLSizeMake(1,1,1),MTLSizeMake(8,1,1));enc_c_end(ce);
    id<MTLBuffer> outputs[8];size_t offsets[8];g_exec_next=next;
    for(int i=0;i<8;i++)assert(title_batch_prepare(payload[i],&outputs[i],&offsets[i]));
    assert(g_title_batch_groups==1 && g_title_batch_draws==8);
    assert(mtl_wait(mtl_sub_commit(),5000000000ull));assert(!mtl_last_commit_error());
    for(int i=0;i<8;i++){
        uint32_t n=i%4==0?0:i%4==1?1:i%4==2?3:99,words=i%2?4:5;
        const uint32_t *actual=(const uint32_t *)((uint8_t *)outputs[i].contents+offsets[i]);
        for(int d=0;d<3;d++)for(int w=0;w<words;w++)assert(actual[d*words+w]==(d<n?source[i*7+d*7+w]:0));
    }
    // Run the real indirect rendering path twice against a closed-form image.
    // Host-only render target; no game shader or game assets are used.
    id<MTLLibrary> graphics=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;vertex float4 v(uint i[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[i],.5,1);}fragment float4 f(){return float4(.0625,0,0,0);}" options:nil error:&error];assert(graphics);
    pr->sh[0]->fn=[graphics newFunctionWithName:@"v"];pr->sh[1]->fn=[graphics newFunctionWithName:@"f"];pr->sh[1]->rf.color_mask=1;
    tex_t color={.serial=99002};color.d.width=color.d.height=8;color.d.depth=color.d.samples=color.d.levels=1;color.d.target=NVN_TEXTURE_TARGET_2D;color.d.format=NVN_FORMAT_RGBA32F;
    commands render={0};p_set_rt rt={.n=1};rt.color[0]=&color;
    emit(&render,OP_SET_RT,&rt,sizeof rt);p_clear_color clear={.index=0,.mask=15};emit(&render,OP_CLEAR_COLOR,&clear,sizeof clear);
    for(int i=0;i<8;i++){
        p[i].type=-1;p[i].primitive=NVN_DRAW_PRIMITIVE_TRIANGLES;p[i].args=(uintptr_t)(source+i*21);
        for(int d=0;d<3;d++){uint32_t *a=source+i*21+d*7;a[0]=3;a[1]=1;a[2]=a[3]=0;}
        emit(&render,OP_MULTI_DRAW,&p[i],sizeof p[i]);
    }
    emit(&render,OP_END,NULL,0);
    op_hdr noop={OP_END,8};mtl_exec((const uint8_t *)&noop);
    for(int reference=0;reference<2;reference++){
        state_reset();memset(&R,0,sizeof R);S.prog=&program;S.color.blend_en=1;S.blend[0].dst_rgb=NVN_BLEND_FUNC_ONE;
        // Disable collection by its explicit RO proof for the reference only.
        pr->sh[0]->range_ro=pr->sh[1]->range_ro=reference!=0;
        id<MTLBuffer> readback=[g_dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
        mtl_sub_begin();uint64_t before=g_stat_pass;mtl_exec(render.bytes);rp_end();
        fprintf(stderr,"render reference=%d passes=%llu\n",!reference,(unsigned long long)(g_stat_pass-before));
        assert(g_stat_pass-before==(reference?1:8));
        [blit() copyFromTexture:tex_mtl(&color) sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(8,8,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:128 destinationBytesPerImage:1024];
        assert(mtl_wait(mtl_sub_commit(),5000000000ull));assert(!mtl_last_commit_error());
        fprintf(stderr,"first pixel=%g counts=%u,%u,%u,%u\n",((float *)readback.contents)[0],counts[0],counts[1],counts[2],counts[3]);
        for(int pixel=0;pixel<64;pixel++)assert(((float *)readback.contents)[pixel*4]==.875f);
    }
    mtl_pool_del(memory);free(memory);
    puts("Indirect batch: 8 GPU-written count/stride/base-ID cases, alias/write/reflection guards and replay-state isolation passed");
}return 0;}
