// Included after replay state/reflection helpers. Only immutable flattened
// submission commands are scanned. The scanner never calls state_op: it owns
// its stage bindings and cannot leak a future viewport/scissor/program into S/R.
enum { TITLE_BATCH_MAX=256 };
typedef struct { uint64_t src,count,dst;uint32_t maximum,stride,words,pad; } title_batch_request;
_Static_assert(sizeof(title_batch_request)==40,"MSL Request ABI");
typedef struct { const p_multi_draw *command;size_t offset; } title_batch_entry;
static title_batch_entry g_title_batch[TITLE_BATCH_MAX];
static unsigned g_title_batch_n,g_title_batch_at;
static id<MTLBuffer> g_title_batch_output;
static uint64_t g_title_batch_groups,g_title_batch_draws;
static void title_batch_reset(void){g_title_batch_n=g_title_batch_at=0;g_title_batch_output=nil;}
void mtl_title_batch_stats(uint64_t *groups,uint64_t *requests){*groups=g_title_batch_groups;*requests=g_title_batch_draws;}
static int title_batch_on(void){
#if DM_NVN_M3
    return 0; // Pointer-table residency proof below is for the Metal 4 path.
#endif
    static int on=-1;static uint64_t polled=~0ull;
    if(on<0){const char *v=getenv("DM_NVN_INDIRECT_BATCH");on=!(v&&!strcmp(v,"0"));}
    uint64_t f=atomic_load(&g_cur_frame);
    if(f!=polled && !(f%60)){
        polled=f;const char *path=getenv("DM_NVN_INDIRECT_BATCH_CONTROL");
        if(path){FILE *file=fopen(path,"r");if(file){int v=fgetc(file);fclose(file);if((v=='0'||v=='1') && on!=v-'0'){on=v-'0';MLOG("[indirect-batch] policy=%d frame=%llu",on,(unsigned long long)f);}}}
    }
    return on;
}
static int title_ranges_overlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m){
    if(!n||!m)return 0;
    if(a>UINT64_MAX-n || b>UINT64_MAX-m)return 1;
    return a<b+m && b<a+n;
}
static int title_batch_input_safe(const p_multi_draw *p){
    if(p->maximum<1 || p->maximum>64 || p->stride<(p->type<0?16:20) || (p->stride&3))return 0;
    uint64_t size=(uint64_t)(p->maximum-1)*p->stride+(p->type<0?16:20);
    // Rendering in this segment can only write these fixed attachments. Test
    // the whole allocation, not just texture serials or the selected mip.
    for(int i=-1;i<R.rt.n && i<8;i++){
        const tex_t *t=i<0?R.rt.depth:R.rt.color[i];if(!t)continue;
        if(!t->mem){if(t->pool)return 0;continue;} // Host-only Metal texture has no guest allocation to alias.
        if(!t->L.size || title_ranges_overlap(p->args,size,(uintptr_t)t->mem,t->L.size) ||
           title_ranges_overlap(p->count,4,(uintptr_t)t->mem,t->L.size))return 0;
    }
    return R.has_rt;
}
static int title_batch_program_ro(const prog_t *p){
    // Future programs must already have validated reflection. Do not compile or
    // resolve unobserved shaders merely because lookahead saw a binding.
    NvProg *q=p && p->serial?serial_get(p->serial):nil;
    return rt_range_pr_ro(q);
}
static void title_batch_reject(unsigned reason,unsigned op){
    static uint64_t counts[4],reported=~0ull;counts[reason]++;
    uint64_t frame=atomic_load(&g_cur_frame);
    if(!(frame%300) && reported!=frame){reported=frame;MLOG("[indirect-batch] eligibility frame=%llu input=%llu program=%llu short=%llu stop_op=%u",(unsigned long long)frame,(unsigned long long)counts[1],(unsigned long long)counts[2],(unsigned long long)counts[3],op);}
}
static unsigned title_batch_collect(const p_multi_draw *first,const uint8_t *next){
    g_title_batch_n=g_title_batch_at=0;
    if(!title_batch_on())return 0;
    if(!title_batch_input_safe(first)){title_batch_reject(1,0);return 0;}
    if(!title_batch_program_ro(S.prog)){title_batch_reject(2,0);return 0;}
    g_title_batch[g_title_batch_n++]=(title_batch_entry){first,0};
    const prog_t *program=S.prog;nvn55_bound_stage stages[6];memcpy(stages,S.program_stages,sizeof stages);
    const uint8_t *cursor=next;unsigned stop_op=0;
    for(unsigned operations=0;cursor && operations<8192 && g_title_batch_n<TITLE_BATCH_MAX;operations++){
        op_hdr h;memcpy(&h,cursor,sizeof h);if(h.size<8 || (h.size&7))break;
        const void *a=cursor+8;stop_op=h.op;
        switch(h.op){
            case OP_MULTI_DRAW:
                if(!title_batch_program_ro(program) || !title_batch_input_safe(a))goto done;
                g_title_batch[g_title_batch_n++]=(title_batch_entry){a,0};break;
            case OP_DRAW:case OP_DRAW_IDX:if(!title_batch_program_ro(program))goto done;break;
            case OP_BIND_PROGRAM:{const p_bind_program *p=a;program=combine_title_prog(p->prog,(unsigned)p->stages,stages);break;}
            case OP_SET_RT:if(!rt_same(&R.rt,a))goto done;break;
            // State and descriptor bindings do not write guest GPU memory.
            case OP_BEGIN:case OP_BACKEND_HINT:case OP_BARRIER:
            case OP_SCISSOR:case OP_BIND_STATE:case OP_BIND_VATTR:case OP_BIND_VSTREAM:case OP_BIND_VBUF:
            case OP_BIND_UBO:case OP_BIND_SSBO:case OP_BIND_TEX:case OP_BIND_SAMP:case OP_BIND_IMG:
            case OP_SET_TEX_POOL:case OP_SET_SAMP_POOL:case OP_STENCIL:case OP_POLY_OFFSET:
            case OP_VIEWPORTS:case OP_DEPTH_RANGE:case OP_BLEND_COLOR:case OP_ALPHA_REF:
            case OP_DEPTH_CLAMP:case OP_DEPTH_BOUNDS:case OP_COPY_STRIDE:break;
            // Copies, uploads, clears, compute, events, queries, control flow,
            // external shader writes and unknown operations end the proof.
            default:goto done;
        }
        cursor+=h.size;
    }
done:
    if(g_title_batch_n<2){g_title_batch_n=0;title_batch_reject(3,stop_op);}
    return g_title_batch_n;
}
static int title_batch_take(const p_multi_draw *p,id<MTLBuffer> __strong *output,size_t *offset){
    if(g_title_batch_at>=g_title_batch_n || g_title_batch[g_title_batch_at].command!=p){g_title_batch_n=g_title_batch_at=0;return 0;}
    *output=g_title_batch_output;*offset=g_title_batch[g_title_batch_at++].offset;return 1;
}
static int title_batch_prepare(const p_multi_draw *first,id<MTLBuffer> __strong *output,size_t *offset){
    if(title_batch_take(first,output,offset))return 1;
    if(!title_batch_collect(first,g_exec_next))return 0;
    static id<MTLComputePipelineState> pipeline;
#if !DM_NVN_M3
    static id<MTL4ArgumentTable> table;
#endif
    if(!pipeline){NSError *error=nil;id<MTLLibrary> lib=[g_dev newLibraryWithSource:@(nvn55_indirect_batch_msl) options:nil error:&error];
        if(lib)pipeline=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"prepare_batch"] error:&error];
        if(!pipeline)MDIE("indirect batch pipeline: %s",error.description.UTF8String);
#if !DM_NVN_M3
        MTL4ArgumentTableDescriptor *d=[MTL4ArgumentTableDescriptor new];d.maxBufferBindCount=2;table=[g_dev newArgumentTableWithDescriptor:d error:&error];if(!table)MDIE("indirect batch table");
#endif
        MLOG("[indirect-batch] GPU preparation enabled; RO segments only, original draws retained");
    }
    size_t total=0;
    for(unsigned i=0;i<g_title_batch_n;i++){const p_multi_draw *p=g_title_batch[i].command;g_title_batch[i].offset=total;total+=(size_t)p->maximum*(p->type<0?16:20);}
    id<MTLBuffer> result,requests,params;size_t base=arena_alloc(total,&result),roff=arena_alloc(g_title_batch_n*sizeof(title_batch_request),&requests),poff=arena_alloc(16,&params);g_title_batch_output=result;
    title_batch_request *r=(title_batch_request *)((uint8_t *)requests.contents+roff);
    for(unsigned i=0;i<g_title_batch_n;i++){
        const p_multi_draw *p=g_title_batch[i].command;unsigned words=p->type<0?4:5;void *buffer;uint64_t unused,src,count;
        if(!mtl_gpu_addr(p->args,(uint64_t)(p->maximum-1)*p->stride+words*4,&buffer,&unused,&src) || !mtl_gpu_addr(p->count,4,&buffer,&unused,&count))MDIE("indirect batch input outside pools");
        g_title_batch[i].offset+=base;r[i]=(title_batch_request){src,count,g_title_batch_output.gpuAddress+g_title_batch[i].offset,(uint32_t)p->maximum,(uint32_t)p->stride/4,words,0};
    }
    *(uint32_t *)((uint8_t *)params.contents+poff)=g_title_batch_n;
    rp_end();if(g_blit){enc_b_end(g_blit);g_blit=nil;}
    CENC encoder=enc_c_begin(NULL);enc_c_pso(encoder,pipeline);
#if DM_NVN_M3
    [encoder setBuffer:requests offset:roff atIndex:0];[encoder setBuffer:params offset:poff atIndex:1];
#else
    [encoder setArgumentTable:table];[table setAddress:requests.gpuAddress+roff atIndex:0];[table setAddress:params.gpuAddress+poff atIndex:1];
#endif
    enc_c_dispatch(encoder,MTLSizeMake((g_title_batch_n+31)/32,1,1),MTLSizeMake(32,1,1));enc_c_end(encoder);args_dirty_all();
    g_title_batch_groups++;g_title_batch_draws+=g_title_batch_n;
    static uint64_t report=~0ull;uint64_t frame=atomic_load(&g_cur_frame);
    if(report!=frame && !(frame%300)){report=frame;MLOG("[indirect-batch] frame=%llu groups=%llu requests=%llu last_group=%u",(unsigned long long)frame,(unsigned long long)g_title_batch_groups,(unsigned long long)g_title_batch_draws,g_title_batch_n);}
    return title_batch_take(first,output,offset);
}
