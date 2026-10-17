#define DM_BAYONETTA3 1
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_snapshot.h"
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_control.h"
static int readable(uint64_t a,size_t n){return a && n<1024*1024;}
int main(void){
    uint32_t ctl[0x880/4]={0};ctl[0]=0x98761234;ctl[1]=1;ctl[2]=15;ctl[8]=0x850;
    assert(nvn_control_size(ctl)==0x850);ctl[2]=16;ctl[8]=0x880;assert(nvn_control_size(ctl)==0x880);
    ctl[8]=0x10000000;assert(!nvn_control_size(ctl));ctl[8]=0x880;ctl[2]=17;assert(!nvn_control_size(ctl));
    uint64_t textures[40];for(int i=0;i<40;i++)textures[i]=i+1;
    struct {op_hdr h;p_bind_deferred p;op_hdr end;} cmd={{OP_BIND_DEFERRED,32},{OP_BIND_TEX,1,0,40,(uintptr_t)textures},{OP_END,8}};
    // Mutation after recording MUST be observed at submit; frozen submission
    // bytes MUST then survive changes to the original array.
    textures[0]=999;nvn55_stream s={0};assert(nvn55_expand(&s,(void *)&cmd,readable));
    const p_bind_handles *p=(const void *)(s.data+8);assert(p->h[0]==999 && p->n==32);
    textures[0]=123;assert(p->h[0]==999);
    const op_hdr *second=(void *)(s.data+((op_hdr *)s.data)->size);
    p=(const void *)((const uint8_t *)second+8);assert(p->first==32 && p->n==8 && p->h[0]==33);free(s.data);
    NVNbufferRange rg={0x123400,64};cmd.p=(p_bind_deferred){OP_BIND_UBO,0,3,1,(uintptr_t)&rg};
    s=(nvn55_stream){0};assert(nvn55_expand(&s,(void *)&cmd,readable));
    const p_bind_buf *b=(const void *)(s.data+8);assert(b->index==3 && b->addr==0x123400 && b->size==64);free(s.data);
    cmd.p.first=16;s=(nvn55_stream){0};assert(!nvn55_expand(&s,(void *)&cmd,readable));free(s.data);
    uint64_t combined=123 | (45ull<<20);cmd.p=(p_bind_deferred){OP_BIND_COMBINED,4,7,1,(uintptr_t)&combined};
    s=(nvn55_stream){0};assert(nvn55_expand(&s,(void *)&cmd,readable));
    const op_hdr *th=(void *)s.data;assert(th->op==OP_BIND_TEX);p=(void *)(s.data+8);assert(p->h[0]==combined);
    th=(void *)(s.data+th->size);assert(th->op==OP_BIND_SAMP);p=(void *)((uint8_t *)th+8);assert(p->h[0]==(45ull<<20));free(s.data);
    puts("NVN55 deferred timing, ranges and chunking passed");
}
