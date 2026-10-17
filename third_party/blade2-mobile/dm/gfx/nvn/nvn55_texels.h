#pragma once
#include "nvn_obj.h"
#include "../tex/nvn_deswizzle.h"
// Region writes preserve all texels outside the region, including mip/layer data.
static int nvn55_write_storage(const tex_t *t,unsigned level,unsigned layer,const NVNcopyRegion *r,const uint8_t *src,size_t row,size_t img){
    if(!t->mem || !src || !r || level>=t->d.levels || r->xoffset<0 || r->yoffset<0 || r->zoffset<0 || r->width<=0 || r->height<=0 || r->depth<=0)return 0;
    int bw,bh,bpb=nvn_fmt_bpb(t->d.format,&bw,&bh);if(!bpb)return 0;
    uint32_t w=t->d.width>>level,h=t->d.height>>level,zmax=t->d.target==2?t->d.depth>>level:t->L.layers-layer;
    if(!w)w=1;if(!h)h=1;if(!zmax)zmax=1;
    if((uint64_t)r->xoffset+r->width>w || (uint64_t)r->yoffset+r->height>h || (uint64_t)r->zoffset+r->depth>zmax || r->xoffset%bw || r->yoffset%bh)return 0;
    size_t wb=(size_t)((r->width+bw-1)/bw)*bpb,hb=(r->height+bh-1)/bh;
    if(!row)row=wb;if(!img)img=row*hb;if(row<wb || img<row*hb)return 0;
    for(int z=0;z<r->depth;z++){
        uint32_t rb,rows,slices,bp;uint64_t base;unsigned th,td;
        unsigned sl=t->d.target==2?layer:layer+r->zoffset+z;
        if(nvn_deswizzle_geom(&t->d,level,sl,&rb,&rows,&slices,&base,&th,&td,&bp))return 0;
        for(size_t y=0;y<hb;y++)for(size_t x=0;x<wb;x++){
            uint64_t o=base+nvn_bl_offset(r->xoffset/bw*bpb+x,r->yoffset/bh+y,t->d.target==2?r->zoffset+z:0,rb,rows,th,td);
            if(o>=t->L.size)return 0;t->mem[o]=src[z*img+y*row+x];
        }
    }
    return 1;
}
