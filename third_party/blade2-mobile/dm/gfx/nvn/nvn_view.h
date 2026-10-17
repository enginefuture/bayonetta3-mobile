#pragma once
#include "nvn_obj.h"
static inline view_t nvn_view_decode(const NVNtextureView *v){
    view_t o={0};if(!v)return o;
#if DM_BAYONETTA3
    uint64_t w;memcpy(&w,v,8);const uint8_t *p=(const uint8_t *)v;
    o.min_layer=w&0xffff;o.nlayers=(w>>16)&0xffff;o.base_level=(w>>32)&255;o.nlevels=(w>>40)&255;o.target=(w>>48)&255;
    o.set_levels=(w>>56)&1;o.set_layers=(w>>57)&1;o.set_format=(w>>58)&1;o.set_swizzle=(w>>59)&1;o.set_ds_mode=(w>>60)&1;o.set_target=(w>>61)&1;o.ds_mode=(w>>62)&3;
    memcpy(&o.format,p+8,4);memcpy(o.swizzle,p+12,4);
#else
    memcpy(&o,v,sizeof o);
#endif
    return o;
}
static inline void nvn_view_encode(NVNtextureView *v,const view_t *o){
#if DM_BAYONETTA3
    uint64_t w=((uint64_t)o->min_layer&0xffff)|((uint64_t)o->nlayers&0xffff)<<16|((uint64_t)o->base_level&255)<<32|((uint64_t)o->nlevels&255)<<40|((uint64_t)o->target&255)<<48;
    w|=(uint64_t)!!o->set_levels<<56|(uint64_t)!!o->set_layers<<57|(uint64_t)!!o->set_format<<58|(uint64_t)!!o->set_swizzle<<59|(uint64_t)!!o->set_ds_mode<<60|(uint64_t)!!o->set_target<<61|(uint64_t)(o->ds_mode&3)<<62;
    memcpy(v,&w,8);memcpy((uint8_t *)v+8,&o->format,4);memcpy((uint8_t *)v+12,o->swizzle,4);
#else
    memcpy(v,o,sizeof *o);
#endif
}
