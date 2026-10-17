#include <stddef.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_texels.h"
int main(void){
    tex_t t={0};t.d=(nvn_texdesc){.target=1,.format=0x25,.width=8,.height=8,.depth=1,.levels=2};nvn_tex_layout(&t.d,&t.L);
    t.mem=malloc(t.L.size);memset(t.mem,0xCC,t.L.size);
    uint8_t src[32];for(int i=0;i<32;i++)src[i]=i;
    NVNcopyRegion r={.xoffset=2,.yoffset=3,.zoffset=0,.width=2,.height=2,.depth=1};
    assert(nvn55_write_storage(&t,0,0,&r,src,16,32));
    uint8_t linear[256];assert(!nvn_deswizzle(&t.d,0,0,t.mem,linear,32));
    for(int y=0;y<8;y++)for(int x=0;x<32;x++)assert(linear[y*32+x]==(y>=3 && y<5 && x>=8 && x<16?src[(y-3)*16+x-8]:0xCC));
    uint8_t mip[64];assert(!nvn_deswizzle(&t.d,1,0,t.mem,mip,16));for(int i=0;i<64;i++)assert(mip[i]==0xCC);
    r.width=99;assert(!nvn55_write_storage(&t,0,0,&r,src,16,32));free(t.mem);puts("Texture region write preserves outside texels and mip data");
}
