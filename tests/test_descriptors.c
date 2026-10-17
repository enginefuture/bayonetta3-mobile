#define DM_BAYONETTA3 1
#include <assert.h>
#include <stdio.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_obj.h"
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_descriptors.h"
_Static_assert(sizeof(dpool_t)<=sizeof(NVNtexturePool),"pool namespace must fit guest object");
int main(void){
 nvn55_desc_table table={0};uint32_t a,b,alias,sampler;
 assert(nvn55_desc_namespace(&table,0x100000,0x200,32768,0,&a));
 assert(nvn55_desc_namespace(&table,0x100000,0x100200,32768,0,&b));
 assert(a==0 && b==32768);
 assert(nvn55_desc_namespace(&table,0x100000,0x200,32768,0,&alias) && alias==a);
 assert(nvn55_desc_namespace(&table,0x100000,0x200,512,1,&sampler) && sampler==0);
 // The same guest descriptor 257 alternates between two independent entries;
 // switching back must recover the first, with no mutation of its raw handle.
 int tex[65536]={0};tex[nvn55_desc_slot(a,32768,257)]=11;tex[nvn55_desc_slot(b,32768,257)]=22;
 assert(tex[nvn55_desc_slot(a,32768,257)]==11);
 assert(tex[nvn55_desc_slot(b,32768,257)]==22);
 assert(!nvn55_desc_slot(b,32768,32768));assert(!nvn55_desc_slot(b,32768,0));
 assert(!nvn55_desc_namespace(&table,0x100000,0x200,32,0,&alias));
 assert(!nvn55_desc_namespace(&table,0x200000,0,1<<20,0,&alias));
 puts("Descriptor pools isolate identical indices, share identical storage, and reject overflow");
}
