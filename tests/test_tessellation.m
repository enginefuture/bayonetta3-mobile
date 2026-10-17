#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_mtl.m"
void *front_metal_layer(void){return NULL;}
module_t *module_of(const void *p){(void)p;return NULL;}
module_t g_mod[MAX_MOD];int g_nmod;uint64_t g_t0_ns;
void svc_thread_dump(void){}
uint64_t now_ns(void){return bp_now();}
uint64_t nvn_new_serial(void){static uint64_t s=190000;return ++s;}
static NvShader *fixture(id<MTLLibrary>lib,const char *fn,int stage){NvShader*s=[NvShader new];s->fn=[lib newFunctionWithName:@(fn)];s->stage=stage;return s;}
int main(int argc,const char **argv){@autoreleasepool{
 BOOL index16=argc>1&&!strcmp(argv[1],"index16"),arrays=argc>1&&!strcmp(argv[1],"arrays"),single=argc>1&&!strcmp(argv[1],"non-instanced"),empty=argc>1&&!strcmp(argv[1],"empty-scissor");
 BOOL attributes=argc>1&&!strcmp(argv[1],"instance-attributes");
 setenv("DM_TESS_TRACE","1",1);mtl_init();NSError *error=nil;
 NSString *source=@"#include <metal_stdlib>\nusing namespace metal;struct P{float4 v[32];float4 p;};struct I{float4 p[[attribute(0)]];};\n"
 "kernel void vs(I i[[stage_in]],device P*out[[buffer(2)]],uint3 g[[thread_position_in_grid]],uint3 n[[grid_size]],constant uint*param[[buffer(3)]]){P p={};p.p=i.p;p.p.x+=float(g.y+param[3]-5u)*.95;out[g.y*n.x+g.x]=p;}\n"
 "kernel void tc(device const P*i[[buffer(1)]],device P*o[[buffer(2)]],constant uint*param[[buffer(3)]],device MTLTriangleTessellationFactorsHalf*f[[buffer(4)]],uint x[[thread_position_in_grid]]){o[x]=i[x];if(x%3==0){uint p=x/3;f[p].edgeTessellationFactor[0]=4;f[p].edgeTessellationFactor[1]=4;f[p].edgeTessellationFactor[2]=4;f[p].insideTessellationFactor=4;}}\n"
 "struct O{float4 p[[position]];};[[patch(triangle,3)]]vertex O te(device const P*i[[buffer(1)]],constant uint*param[[buffer(3)]],float3 uv[[position_in_patch]],uint p[[patch_id]],uint instance[[instance_id]],device atomic_uint*probe[[buffer(5)]]){uint sample=atomic_fetch_add_explicit(probe,1u,memory_order_relaxed);atomic_fetch_min_explicit(probe+1,instance,memory_order_relaxed);atomic_fetch_max_explicit(probe+2,instance,memory_order_relaxed);atomic_fetch_max_explicit(probe+3,p,memory_order_relaxed);uint x=((instance-param[3])*param[2]+p)*3;O o;o.p=i[x].p*uv.x+i[x+1].p*uv.y+i[x+2].p*uv.z;o.p.z-=.4*27*uv.x*uv.y*uv.z;if(sample<256)((device float4*)(probe+4))[sample]=o.p;return o;}fragment float4 fs(){return float4(1,0,0,1);}";
 if(attributes){source=[source stringByReplacingOccurrencesOfString:@"struct I{float4 p[[attribute(0)]];}" withString:@"struct I{float4 p[[attribute(0)]];float shift[[attribute(1)]];}"];source=[source stringByReplacingOccurrencesOfString:@"p.p.x+=float(g.y+param[3]-5u)*.95" withString:@"p.p.xy*=.45;p.p.y+=float(g.y%2)*.9-.45;p.p.x+=i.shift"];}
 id<MTLLibrary>lib=[g_dev newLibraryWithSource:source options:nil error:&error];if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);return 1;}
 NvShader *vs=fixture(lib,"vs",0),*tc=fixture(lib,"tc",3),*te=fixture(lib,"te",4),*fs=fixture(lib,"fs",1);vs->rf.nv=1;vs->rf.v[0].loc=vs->rf.v[0].nvn=0;
 strlcpy(vs->key,"1111111111111111_tv",sizeof vs->key);strlcpy(tc->key,"2222222222222222_tc",sizeof tc->key);strlcpy(te->key,"3333333333333333_te",sizeof te->key);
 g_tess_shaders=[NSMutableDictionary dictionaryWithDictionary:@{@"1111111111111111_tv":vs,@"2222222222222222_tc":tc,@"3333333333333333_te":te}];
 prog_t program={.serial=198001};NvProg*pr=[NvProg new];pr->sh[0]=vs;pr->sh[1]=fs;strlcpy(pr->tesskeys[0],"2222222222222222",17);strlcpy(pr->tesskeys[1],"3333333333333333",17);serial_put(program.serial,pr);
 void *memory;assert(!posix_memalign(&memory,getpagesize(),getpagesize()));memset(memory,0,getpagesize());mtl_pool_add(memory,getpagesize());float points[16]={9,9,9,1,-.9,-.8,.6,1,-.1,-.8,.6,1,-.5,.8,.6,1};memcpy(memory,points,sizeof points);
 uint32_t *indices=(uint32_t *)((uint8_t*)memory+1024);indices[0]=2;indices[1]=0;indices[2]=1;
 if(index16){uint16_t small[3]={2,0,1};memcpy(indices,small,sizeof small);}
 tex_t color={.serial=198002},depth={.serial=198003};color.d.width=depth.d.width=192;color.d.height=depth.d.height=96;color.d.depth=depth.d.depth=1;color.d.levels=depth.d.levels=1;color.d.samples=depth.d.samples=1;color.d.target=depth.d.target=NVN_TEXTURE_TARGET_2D;color.d.format=NVN_FORMAT_RGBA32F;depth.d.format=NVN_FORMAT_DEPTH32F;
 state_reset();memset(&R,0,sizeof R);S.prog=&program;S.patch_size=3;S.nattr=1;S.attr[0].fmt=NVN_FORMAT_RGBA32F;S.stream[0].stride=16;S.vbuf[0]=(NVNbufferRange){(uintptr_t)memory,64};S.ds.dt=1;
 if(attributes){float shifts[8]={9,9,9,9,9,0,.95,9};memcpy((uint8_t*)memory+2048,shifts,sizeof shifts);vs->rf.nv=2;vs->rf.v[1].loc=vs->rf.v[1].nvn=1;S.nattr=2;S.attr[1].fmt=NVN_FORMAT_R32F;S.attr[1].stream=1;S.stream[1].stride=4;S.stream[1].divisor=2;S.vbuf[1]=(NVNbufferRange){(uintptr_t)memory+2048,sizeof shifts};}
 R.has_rt=1;R.rt.n=1;R.rt.color[0]=&color;R.rt.depth=&depth;R.clear_c[0]=R.clear_d=1;R.cd=1;
 if(empty){R.has_sc=1;R.sc=(p_scissor){200,0,10,10};}
 p_draw_idx draw_indexed={.prim=NVN_DRAW_PRIMITIVE_PATCHES,.itype=2,.count=3,.base_vertex=1,.base_instance=5,.instances=2,.ibuf=(uintptr_t)indices};
 if(index16)draw_indexed.itype=1;if(single)draw_indexed.instances=0;if(attributes)draw_indexed.instances=4;
 p_draw draw_arrays={.prim=NVN_DRAW_PRIMITIVE_PATCHES,.first=1,.count=3,.base_instance=5,.instances=2};
 mtl_sub_begin();if(arrays)title_tess_draw(&draw_arrays,NULL);else title_tess_draw(NULL,&draw_indexed);rp_flush();rp_end();
 id<MTLBuffer>rgb=[g_dev newBufferWithLength:192*96*16 options:MTLResourceStorageModeShared],z=[g_dev newBufferWithLength:192*96*4 options:MTLResourceStorageModeShared];
 res_add(rgb);res_add(z);res_commit();
 [blit() copyFromTexture:tex_mtl(&color) sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(192,96,1) toBuffer:rgb destinationOffset:0 destinationBytesPerRow:192*16 destinationBytesPerImage:192*96*16];
 [blit() copyFromTexture:tex_mtl(&depth) sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(192,96,1) toBuffer:z destinationOffset:0 destinationBytesPerRow:192*4 destinationBytesPerImage:192*96*4];
 assert(mtl_wait(mtl_sub_commit(),10000000000ull));assert(!mtl_last_commit_error());
 const float *pixels=rgb.contents,*zs=z.contents;int left=0,right=0,curved=0,quadrants[4]={0};float minimum=1;
 for(int y=0;y<96;y++)for(int x=0;x<192;x++){int i=y*192+x;if(pixels[4*i]>.9){if(x<96)left++;else right++;quadrants[(x>=96)+2*(y>=48)]++;if(zs[i]<.5)curved++;minimum=fminf(minimum,zs[i]);}}
 printf("Native tessellation fixture %s: left=%d right=%d curved=%d min-depth=%g\n",argc>1?argv[1]:"index32",left,right,curved,minimum);
 if(empty)assert(left==0&&right==0&&curved==0&&g_tess_binding==0);
 else assert(left>1000&&(single?right==0:right>1000)&&curved>1000&&minimum<.4);
 if(attributes)for(int i=0;i<4;i++)assert(quadrants[i]>300);
 mtl_pool_del(memory);free(memory);puts("Production tessellation GPU case passed");
}return 0;}
