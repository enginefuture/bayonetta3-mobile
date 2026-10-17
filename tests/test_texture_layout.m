#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_mtl.m"
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn55_texels.h"
void *front_metal_layer(void){return NULL;}
module_t *module_of(const void *p){(void)p;return NULL;}
module_t g_mod[MAX_MOD];int g_nmod;uint64_t g_t0_ns;
void svc_thread_dump(void){}
uint64_t now_ns(void){return bp_now();}
uint64_t nvn_new_serial(void){static uint64_t s=290000;return ++s;}

// Independent, explicit golden GOB locations for 1024/1026 ASTC 6x6,
// packaged tileH=3/tileW=4. Do not build the input using production swizzle.
static size_t golden(unsigned x,unsigned y,unsigned level){
    static const size_t bases[3]={0,589824,851968};
    static const unsigned pitches[3]={48,32,11},heights[3]={8,8,8};
    unsigned bh=heights[level];size_t gob=(y/(8*bh))*pitches[level]*bh+(x/64)*bh+(y/8)%bh;
    return bases[level]+gob*512+(x%64/32)*256+(y%8/2)*64+(x%32/16)*32+(y%2)*16+x%16;
}
// Independent mip tables for 512-square BC1/BC6H, including the sparse mip
// tail and a 64-KiB face stride. Golden addressing never calls the layout code.
static void sparse_mips(int format,int cube){
    static const size_t base8[]={0,131072,163840,172032,174080,174592,175104,175616,176128,176640};
    static const size_t base16[]={0,262144,327680,344064,348160,349184,349696,350208,350720,351232};
    static const unsigned pitch8[]={16,8,4,2,1,1,1,1,1,1},pitch16[]={32,16,8,4,2,1,1,1,1,1},bh[]={8,8,4,2,1,1,1,1,1,1};
    unsigned bpb=format==0x42?8:16;const size_t *bases=bpb==8?base8:base16;const unsigned*pitches=bpb==8?pitch8:pitch16;
    size_t face=cube?(bpb==8?196608:393216):(bpb==8?177152:351744);unsigned faces=cube?6:1;
    tex_t t={.serial=nvn_new_serial()};t.d=(nvn_texdesc){.target=cube?8:1,.format=format,.flags=4,.width=512,.height=512,.depth=1,.levels=10,.pkg_block_h=4,.pkg_tile_w=4};nvn_tex_layout(&t.d,&t.L);
    assert(t.L.layer_size==face&&t.L.size==face*faces);
    size_t allocation=(t.L.size+getpagesize()-1)&~(getpagesize()-1);void*memory;assert(!posix_memalign(&memory,getpagesize(),allocation));memset(memory,0xa7,allocation);t.mem=memory;mtl_pool_add(memory,allocation);
    for(unsigned f=0;f<faces;f++)for(unsigned l=0;l<10;l++){
        unsigned w=MAX(512u>>l,1u),n=(w+3)/4,row=n*bpb;assert(nvn_tex_level_offset(&t.d,l)==bases[l]);assert(nvn_tex_level_row_bytes(&t.d,l)==pitches[l]*64);
        uint8_t*expected=malloc(row*n),*linear=malloc(row*n);
        for(unsigned y=0;y<n;y++)for(unsigned x=0;x<row;x++){
            size_t gob=(y/(8*bh[l]))*pitches[l]*bh[l]+(x/64)*bh[l]+(y/8)%bh[l];
            size_t off=f*face+bases[l]+gob*512+(x%64/32)*256+(y%8/2)*64+(x%32/16)*32+(y%2)*16+x%16;
            uint8_t value=(f*29+l*17+(x/bpb)*7+y*3+x%bpb)&255;expected[y*row+x]=value;((uint8_t*)memory)[off]=value;
        }
        assert(!nvn_deswizzle(&t.d,l,f,memory,linear,row));assert(!memcmp(expected,linear,row*n));free(expected);free(linear);
    }
    if(cube){
        // Edit one BC block on face 5, at the small-mip sparse-width boundary.
        NVNcopyRegion region={.xoffset=12,.yoffset=4,.width=4,.height=4,.depth=1};uint8_t block[16];
        for(unsigned i=0;i<bpb;i++)block[i]=((5*29+17+3*7+3+i)&255)^0x5a;
        assert(nvn55_write_storage(&t,1,5,&region,block,bpb,bpb));
        uint8_t *linear=malloc(64*64*bpb);assert(!nvn_deswizzle(&t.d,1,5,memory,linear,64*bpb));assert(!memcmp(linear+(64+3)*bpb,block,bpb));free(linear);
    }
    // Production Metal 4 upload followed by independent compressed-block readback.
    mtl_sub_begin();id<MTLTexture>texture=tex_mtl(&t);assert(texture);assert(mtl_wait(mtl_sub_commit(),10000000000ull));assert(!mtl_last_commit_error());
    for(unsigned f=0;f<faces;f++)for(unsigned l=0;l<10;l++){
        unsigned w=MAX(512u>>l,1u),n=(w+3)/4,row=n*bpb,pitch=(row+255)&~255;
        id<MTLBuffer>output=[g_dev newBufferWithLength:pitch*n options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer>cb=[g_q commandBuffer];id<MTLBlitCommandEncoder>bl=[cb blitCommandEncoder];
        [bl copyFromTexture:texture sourceSlice:f sourceLevel:l sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(w,w,1) toBuffer:output destinationOffset:0 destinationBytesPerRow:pitch destinationBytesPerImage:pitch*n];[bl endEncoding];[cb commit];[cb waitUntilCompleted];assert(!cb.error);
        const uint8_t*bytes=output.contents;for(unsigned y=0;y<n;y++)for(unsigned x=0;x<row;x++){
            uint8_t value=(f*29+l*17+(x/bpb)*7+y*3+x%bpb)&255;if(cube&&f==5&&l==1&&y==1&&x/bpb==3)value^=0x5a;
            assert(bytes[y*pitch+x]==value);
        }
    }
    if(cube){nvn_texdesc dense=t.d;dense.pkg_tile_w=0;nvn_texlayout old;nvn_tex_layout(&dense,&old);assert(old.layer_size!=face);}
    mtl_pool_del(memory);free(memory);
}
int main(void){@autoreleasepool{
    mtl_init();assert(sizeof(nvn_texdesc)==36);NSError *error=nil;
    sparse_mips(0x42,0);sparse_mips(0x50,0);sparse_mips(0x42,1);sparse_mips(0x50,1);
    NSString*code=@"#include <metal_stdlib>\nusing namespace metal;kernel void check(texture2d<float,access::read> t[[texture(0)]],constant uint&l[[buffer(0)]],constant float4&expected[[buffer(1)]],device atomic_uint*bad[[buffer(2)]],uint2 p[[thread_position_in_grid]]){float4 v=t.read(p,l);if(any(abs(v-expected)>1.0/255.0))atomic_fetch_add_explicit(bad,1u,memory_order_relaxed);}";
    id<MTLLibrary>lib=[g_dev newLibraryWithSource:code options:nil error:&error];
    id<MTLComputePipelineState>check=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"check"] error:&error];assert(check);
    for(int edge=0;edge<2;edge++){
        tex_t t={.serial=nvn_new_serial()};t.d=(nvn_texdesc){.target=1,.format=0x7d,.flags=4,.width=1024+2*edge,.height=1024+2*edge,.depth=1,.levels=3,.pkg_block_h=4,.pkg_tile_w=4};nvn_tex_layout(&t.d,&t.L);
        assert(t.L.size==897024);assert(nvn_tex_level_offset(&t.d,1)==589824);assert(nvn_tex_level_offset(&t.d,2)==851968);
        assert(nvn_tex_level_row_bytes(&t.d,0)==3072&&nvn_tex_level_row_bytes(&t.d,1)==2048&&nvn_tex_level_row_bytes(&t.d,2)==704);
        size_t allocation=(t.L.size+getpagesize()-1)&~(getpagesize()-1);void *memory;assert(!posix_memalign(&memory,getpagesize(),allocation));memset(memory,0,allocation);t.mem=memory;mtl_pool_add(memory,allocation);
        uint16_t colors[3][4]={{16384,32768,49151,65535},{49151,16384,32768,65535},{8192,57343,32768,65535}};
        for(unsigned l=0;l<3;l++){
            unsigned w=MAX(t.d.width>>l,1u),h=MAX(t.d.height>>l,1u),nx=(w+5)/6,ny=(h+5)/6;
            uint8_t block[16]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff};memcpy(block+8,colors[l],8);
            for(unsigned y=0;y<ny;y++)for(unsigned x=0;x<nx;x++)memcpy((uint8_t*)memory+golden(x*16,y,l),block,16);
            uint8_t *linear=malloc(nx*ny*16);assert(!nvn_deswizzle(&t.d,l,0,memory,linear,nx*16));
            for(unsigned i=0;i<nx*ny;i++)assert(!memcmp(linear+i*16,block,16));free(linear);
            if(l==0){
                nvn_texdesc old=t.d;old.pkg_tile_w=0;linear=malloc(nx*ny*16);assert(!nvn_deswizzle(&old,0,0,memory,linear,nx*16));
                unsigned wrong=0;for(unsigned i=0;i<nx*ny;i++)wrong+=memcmp(linear+i*16,block,16)!=0;
                assert(wrong==2183);free(linear); // Old addressing must reproduce the defect.
            }
        }
        // Region write in the second tile row must preserve padding and mips.
        NVNcopyRegion region={.xoffset=120,.yoffset=384,.width=6,.height=6,.depth=1};uint8_t replacement[16];memcpy(replacement,(uint8_t*)memory+golden(320,64,0),16);
        uint8_t before[16];memcpy(before,replacement,16);replacement[8]^=1;
        assert(nvn55_write_storage(&t,0,0,&region,replacement,16,16));assert(!memcmp((uint8_t*)memory+golden(320,64,0),replacement,16));
        assert(!nvn55_write_storage(&t,0,0,&region,before,15,16));memcpy((uint8_t*)memory+golden(320,64,0),before,16);
        mtl_sub_begin();id<MTLTexture>texture=tex_mtl(&t);assert(texture);assert(mtl_wait(mtl_sub_commit(),10000000000ull));assert(!mtl_last_commit_error());
        for(unsigned l=0;l<3;l++){
            float expected[4];for(int i=0;i<4;i++)expected[i]=colors[l][i]/65535.f;
            id<MTLBuffer>bad=[g_dev newBufferWithLength:16 options:MTLResourceStorageModeShared];id<MTLCommandBuffer>cb=[g_q commandBuffer];id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
            [en setComputePipelineState:check];[en setTexture:texture atIndex:0];[en setBytes:&l length:4 atIndex:0];[en setBytes:expected length:16 atIndex:1];[en setBuffer:bad offset:0 atIndex:2];
            [en dispatchThreads:MTLSizeMake(MAX(t.d.width>>l,1u),MAX(t.d.height>>l,1u),1) threadsPerThreadgroup:MTLSizeMake(16,16,1)];[en endEncoding];[cb commit];[cb waitUntilCompleted];assert(!cb.error);assert(*(uint32_t*)bad.contents==0);
        }
        mtl_pool_del(memory);free(memory);
    }
    puts("Packaged ASTC tile width: CPU/production Metal 4 upload, 1024/1026 edges, three mips and region writes passed");
}return 0;}
