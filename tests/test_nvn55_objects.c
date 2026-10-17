#define DM_BAYONETTA3 1
#include <stddef.h>
#include <stdio.h>
#include <assert.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_view.h"
_Static_assert(sizeof(NVNtexture)==128,"NVN55 texture storage");
_Static_assert(sizeof(tex_t)<=128,"native texture cannot overwrite next object");
_Static_assert(sizeof(NVNtextureView)==16,"NVN55 texture view storage");
int main(void){
 const uint8_t sdk[16]={0xfe,0xff,4,0,7,3,4,0x7f,0x29,0,0,0,2,3,4,5};
 struct {uint64_t before;NVNtextureView v;uint64_t after;} guarded={.before=123,.after=456};
 memcpy(&guarded.v,sdk,16);view_t o=nvn_view_decode(&guarded.v);
 assert(o.min_layer==65534 && o.nlayers==4 && o.base_level==7 && o.nlevels==3 && o.target==4 && o.format==0x29);
 assert(o.set_levels && o.set_layers && o.set_format && o.set_swizzle && o.set_ds_mode && o.set_target && o.ds_mode==1);
 assert(!memcmp(o.swizzle,sdk+12,4));nvn_view_encode(&guarded.v,&o);assert(!memcmp(&guarded.v,sdk,16));
 o=(view_t){0};nvn_view_encode(&guarded.v,&o);for(int i=0;i<16;i++)assert(((uint8_t *)&guarded.v)[i]==0);
 assert(guarded.before==123 && guarded.after==456);puts("NVN55 object sizes, SDK view bitfields and write boundaries passed");
}
