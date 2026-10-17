#pragma once
#include "nvn_obj.h"
#include <stdlib.h>
// Deferred arrays are CPU references read at QueueSubmitCommands, not at record
// time and not from GPU memory. Flatten calls/jumps into a submission-owned
// stream so every Metal lookahead pass sees the same snapshot of those arrays.
typedef struct { uint8_t *data; size_t size,cap,ops; const uint8_t *stack[32]; int depth; } nvn55_stream;
static inline int nvn55_append(nvn55_stream *s,const void *data,size_t n) {
    if(n>64*1024*1024 || s->size>64*1024*1024-n)return 0;
    if(s->size+n>s->cap){size_t c=s->cap?s->cap:4096;while(c<s->size+n)c*=2;void *p=realloc(s->data,c);if(!p)return 0;s->data=p;s->cap=c;}
    memcpy(s->data+s->size,data,n);s->size+=n;return 1;
}
static inline int nvn55_expand(nvn55_stream *s,const uint8_t *p,int (*readable)(uint64_t,size_t)) {
    if(!p || s->depth==32)return 0;
    for(int i=0;i<s->depth;i++)if(s->stack[i]==p)return 0;
    s->stack[s->depth++]=p;
    for(;;){
        if(++s->ops>1000000 || !readable((uintptr_t)p,8))return 0;
        op_hdr h;memcpy(&h,p,8);
        if(h.size<8 || (h.size&7) || h.size>16*1024*1024 || !readable((uintptr_t)p,h.size))return 0;
        if(h.op==OP_END){s->depth--;return 1;}
        if(h.op==OP_JUMP || h.op==OP_CALL){
            if(h.size!=16)return 0;uint64_t target;memcpy(&target,p+8,8);
            if(h.op==OP_JUMP){p=(const uint8_t *)(uintptr_t)target;continue;}
            if(!nvn55_expand(s,(const uint8_t *)(uintptr_t)target,readable))return 0;
        } else if(h.op==OP_BIND_DEFERRED){
            if(h.size!=8+sizeof(p_bind_deferred))return 0;
            p_bind_deferred b;memcpy(&b,p+8,sizeof b);
            int buffer=b.op==OP_BIND_UBO || b.op==OP_BIND_SSBO;
            int handles=b.op==OP_BIND_TEX || b.op==OP_BIND_SAMP || b.op==OP_BIND_IMG || b.op==OP_BIND_COMBINED;
            int limit=buffer?16:b.op==OP_BIND_IMG?32:128;
            if((!buffer&&!handles) || b.stage<0 || b.stage>=6 || b.first<0 || b.n<0 || b.first>limit || b.n>limit-b.first)return 0;
            size_t stride=buffer?sizeof(NVNbufferRange):8;
            if(b.n && (!b.source || (b.source&7) || !readable(b.source,stride*(size_t)b.n)))return 0;
            if(buffer){for(int i=0;i<b.n;i++){
                NVNbufferRange r;memcpy(&r,(const void *)(uintptr_t)(b.source+stride*i),sizeof r);
                struct {op_hdr h;p_bind_buf p;} record={{b.op,8+sizeof(p_bind_buf)},{b.stage,b.first+i,r.address,r.size}};
                if(!nvn55_append(s,&record,sizeof record))return 0;
            }} else for(int i=0;i<b.n;){
                int n=b.n-i;if(n>32)n=32;
                struct {op_hdr h;p_bind_handles p;} record={0};record.h.op=b.op==OP_BIND_COMBINED?OP_BIND_TEX:b.op;
                record.h.size=(uint32_t)((8+offsetof(p_bind_handles,h)+8*n+7)&~7);
                record.p.stage=b.stage;record.p.first=b.first+i;record.p.n=n;
                memcpy(record.p.h,(const void *)(uintptr_t)(b.source+8*i),8*n);
                if(!nvn55_append(s,&record,record.h.size))return 0;
                if(b.op==OP_BIND_COMBINED){record.h.op=OP_BIND_SAMP;for(int j=0;j<n;j++)record.p.h[j]&=~0xFFFFFull;
                    if(!nvn55_append(s,&record,record.h.size))return 0;}
                i+=n;
            }
        } else if(h.op!=OP_BEGIN && !nvn55_append(s,p,h.size))return 0;
        p+=h.size;
    }
}
