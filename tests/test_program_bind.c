#define DM_BAYONETTA3 1
#include <assert.h>
#include <stdio.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_program_bind.h"
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_hmap.h"
static NVNshaderData shader(unsigned char code[0x80],int kind){
 uint32_t m=kind?0x12345678:0,w=(unsigned)kind<<10;memset(code,0,0x80);memcpy(code,&m,4);memcpy(code+0x30,&w,4);
 return (NVNshaderData){(uintptr_t)code,code};
}
int main(void){
 unsigned char a[0x80],b[0x80],f[0x80],c[0x80];
 prog_t va={.serial=1,.nstage=1},vb={.serial=2,.nstage=1},fs={.serial=3,.nstage=1},cs={.serial=4,.nstage=1};
 va.sd[0]=shader(a,1);vb.sd[0]=shader(b,1);fs.sd[0]=shader(f,5);cs.sd[0]=shader(c,0);
 nvn55_bound_stage bound[6]={0};
 assert(nvn55_bind_program(bound,&cs,32));
 // Broad graphics binding must not leave copies of one VS in absent stages.
 assert(nvn55_bind_program(bound,&va,31));assert(bound[0].program==&va && !bound[1].program && !bound[2].program && bound[5].program==&cs);
 assert(nvn55_bind_program(bound,&fs,2));assert(nvn55_bind_program(bound,&vb,1));
 assert(bound[0].program==&vb && bound[1].program==&fs && !bound[3].program);
 assert(nvn55_bind_program(bound,NULL,2));assert(!bound[1].program && bound[0].program==&vb && bound[5].program==&cs);
 prog_t both={.serial=5,.nstage=2};both.sd[0]=va.sd[0];both.sd[1]=fs.sd[0];
 assert(nvn55_bind_program(bound,&both,31));assert(bound[0].program==&both && bound[0].shader==0 && bound[1].shader==1 && bound[5].program==&cs);
 assert(nvn55_bind_program(bound,NULL,0));assert(bound[0].program==&both);
 assert(!nvn55_bind_program(bound,&va,64));
 both.sd[1]=va.sd[0];assert(!nvn55_bind_program(bound,&both,31));assert(bound[0].serial==5);
 // A speculative forward scan must restore stage state before a real partial bind.
 nvn55_bound_stage saved[6];
 assert(nvn55_bind_program(bound,&va,31));memcpy(saved,bound,sizeof saved);
 assert(nvn55_bind_program(bound,&vb,1));assert(nvn55_bind_program(bound,&cs,32));
 memcpy(bound,saved,sizeof saved);assert(nvn55_bind_program(bound,&fs,2));
 assert(bound[0].program==&va && bound[1].program==&fs && bound[5].program==&cs);
 // Independent saved states must not share mutable stage storage.
 assert(nvn55_bind_program(saved,&vb,1));assert(bound[0].program==&va);
 // Cache identity includes pointer/generation/index, independent of struct padding.
 nvn55_bound_stage poisoned[6];memset(poisoned,0xa5,sizeof poisoned);
 for(int i=0;i<6;i++){poisoned[i].program=bound[i].program;poisoned[i].serial=bound[i].serial;poisoned[i].shader=bound[i].shader;}
 uint64_t k1[18],k2[18];nvn55_program_key(bound,k1);nvn55_program_key(poisoned,k2);assert(!memcmp(k1,k2,sizeof k1));
 poisoned[0].serial++;nvn55_program_key(poisoned,k2);assert(memcmp(k1,k2,sizeof k1));
 poisoned[0].serial--;poisoned[0].shader++;nvn55_program_key(poisoned,k2);assert(memcmp(k1,k2,sizeof k1));
 // Wide canonical keys survive hash collisions/growth without generation aliasing.
 nvn_hmap cache={.klen=sizeof k1};
 for(unsigned i=1;i<=10000;i++){poisoned[0].serial=i;nvn55_program_key(poisoned,k2);assert(!nvn_hm_put(&cache,k2,(void *)(uintptr_t)i));}
 for(unsigned i=10000;i;i--){poisoned[0].serial=i;nvn55_program_key(poisoned,k2);assert(nvn_hm_get(&cache,k2)==(void *)(uintptr_t)i);}
 poisoned[0].shader++;nvn55_program_key(poisoned,k2);assert(!nvn_hm_get(&cache,k2));free(cache.keys);free(cache.vals);
 puts("NVN55 graphics/compute binding, absent-stage disable, partial replacement and duplicate rejection passed");
}
