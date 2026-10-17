#pragma once
#include <stdint.h>
// CPU registries use disjoint slots; guest handles keep their original pool-
// relative indices. Two pool objects over identical storage share a namespace.
typedef struct { uintptr_t storage;int64_t off;uint32_t n,base;int sampler; } nvn55_desc_entry;
typedef struct { nvn55_desc_entry entry[128];uint32_t count,next[2]; } nvn55_desc_table;
static inline int nvn55_desc_namespace(nvn55_desc_table *t,uintptr_t storage,int64_t off,int n,int sampler,uint32_t *base){
    if(!storage || off<0 || n<=0 || sampler<0 || sampler>1)return 0;
    for(uint32_t i=0;i<t->count;i++){
        nvn55_desc_entry *e=&t->entry[i];
        if(e->storage==storage && e->off==off && e->sampler==sampler){if(e->n!=(uint32_t)n)return 0;*base=e->base;return 1;}
    }
    if(t->count==128 || (uint32_t)n>(1u<<20)-t->next[sampler])return 0;
    *base=t->next[sampler];t->next[sampler]+=(uint32_t)n;
    t->entry[t->count++]=(nvn55_desc_entry){storage,off,(uint32_t)n,*base,sampler};return 1;
}
static inline int nvn55_desc_slot(uint32_t base,uint32_t n,uint32_t raw){
    return raw && raw<n && base<(1u<<20) && raw<(1u<<20)-base ? (int)(base+raw):0;
}
