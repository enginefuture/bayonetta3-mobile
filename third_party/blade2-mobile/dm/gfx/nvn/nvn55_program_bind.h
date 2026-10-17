#pragma once
#include "nvn_obj.h"
typedef struct { const prog_t *program;uint64_t serial;unsigned shader; } nvn55_bound_stage;
static inline void nvn55_program_key(const nvn55_bound_stage bound[6],uint64_t key[18]){
    // Canonical fields, never hash C struct padding.
    for(unsigned i=0;i<6;i++){key[i*3]=(uintptr_t)bound[i].program;key[i*3+1]=bound[i].serial;key[i*3+2]=bound[i].shader;}
}
static inline int nvn55_shader_stage(const NVNshaderData *s){
    if(!s || !s->control || !s->data)return -1;
    const uint8_t *code=(const uint8_t *)(uintptr_t)s->data;uint32_t magic,word;
    memcpy(&magic,code,4);if(magic!=0x12345678)return 5;
    memcpy(&word,code+0x30,4);
    switch((word>>10)&15){case 1:return 0;case 5:return 1;case 4:return 2;case 2:return 3;case 3:return 4;default:return -1;}
}
static inline int nvn55_bind_program(nvn55_bound_stage bound[6],const prog_t *p,unsigned requested){
    if(requested&~63u || (p && p->nstage>6))return 0;
    if(!requested)return 1;
    unsigned present=0;int index[6]={0};
    if(p)for(unsigned i=0;i<p->nstage;i++){
        int stage=nvn55_shader_stage(&p->sd[i]);if(stage<0 || (present&(1u<<stage)))return 0;
        present|=1u<<stage;index[stage]=(int)i;
    }
    // SDK 55.12 CommandBufferBindProgram (sdk+4c2c00): a matching
    // compute request binds compute; otherwise the program's graphics packet
    // is copied. Requested stages absent from the program are disabled.
    unsigned write=(present&requested&32u)?32u:(present&31u);
    for(unsigned stage=0;stage<6;stage++){
        unsigned bit=1u<<stage;
        if(write&bit)bound[stage]=(nvn55_bound_stage){p,p->serial,(unsigned)index[stage]};
        else if((requested&bit) && !(present&bit))bound[stage]=(nvn55_bound_stage){0};
    }
    return 1;
}
