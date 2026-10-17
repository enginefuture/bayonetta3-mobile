// Dense image motion, current -> previous, in input pixels. This is measured
// image motion, not engine skeletal velocity; disocclusions/transparency can
// produce errors. Frame generation remains an explicit experimental option.
static id<MTLTexture> metalfx_motion(id<MTLCommandBuffer> cb, id<MTLTexture> current, id<MTLTexture> previous) {
    static id<MTLComputePipelineState> reduce,scalar,search,expand;
    static id<MTLTexture> gray[2][4],flow[4],motion;
    static NSUInteger width,height;
    if (!reduce) {
        NSString *source=@"#include <metal_stdlib>\nusing namespace metal;\n"
        "constexpr sampler lin(coord::normalized,address::clamp_to_edge,filter::linear);\n"
        "kernel void reduceGray(texture2d<float,access::sample> src[[texture(0)]],texture2d<half,access::write> dst[[texture(1)]],uint2 p[[thread_position_in_grid]]){if(any(p>=uint2(dst.get_width(),dst.get_height())))return;float2 uv=(float2(p)+.5)/float2(dst.get_width(),dst.get_height());float2 e=.25/float2(dst.get_width(),dst.get_height());float4 c=(src.sample(lin,uv+e)+src.sample(lin,uv-e)+src.sample(lin,uv+float2(e.x,-e.y))+src.sample(lin,uv+float2(-e.x,e.y)))*.25;float v=dot(c.rgb,float3(.299,.587,.114));dst.write(half4(v),p);}\n"
        "kernel void reduceOne(texture2d<float,access::sample> src[[texture(0)]],texture2d<half,access::write> dst[[texture(1)]],uint2 p[[thread_position_in_grid]]){if(any(p>=uint2(dst.get_width(),dst.get_height())))return;float2 uv=(float2(p)+.5)/float2(dst.get_width(),dst.get_height());float2 e=.25/float2(dst.get_width(),dst.get_height());float c=(src.sample(lin,uv+e).x+src.sample(lin,uv-e).x+src.sample(lin,uv+float2(e.x,-e.y)).x+src.sample(lin,uv+float2(-e.x,e.y)).x)*.25;dst.write(half4(c),p);}\n"
        "kernel void matchFlow(texture2d<float,access::sample> cur[[texture(0)]],texture2d<float,access::sample> prev[[texture(1)]],texture2d<float,access::sample> coarse[[texture(2)]],texture2d<half,access::write> dst[[texture(3)]],constant uint& first[[buffer(0)]],uint2 p[[thread_position_in_grid]]){uint2 size=uint2(dst.get_width(),dst.get_height());if(any(p>=size))return;float2 guess=first?float2(0):coarse.sample(lin,(float2(p)+.5)/float2(size)).xy*float2(size)/float2(coarse.get_width(),coarse.get_height());guess=round(guess);float best=1e20;float2 chosen=guess;for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){float2 v=guess+float2(x,y);float cost=.00002*dot(v,v);for(int j=-2;j<=2;j++)for(int i=-2;i<=2;i++){int2 a=clamp(int2(p)+int2(i,j),int2(0),int2(size)-1);int2 b=clamp(a+int2(v),int2(0),int2(size)-1);cost+=abs(cur.read(uint2(a)).x-prev.read(uint2(b)).x);}if(cost<best){best=cost;chosen=v;}}dst.write(half4(half2(chosen),0,0),p);}\n"
        "kernel void expandFlow(texture2d<float,access::sample> src[[texture(0)]],texture2d<half,access::write> dst[[texture(1)]],uint2 p[[thread_position_in_grid]]){uint2 size=uint2(dst.get_width(),dst.get_height());if(any(p>=size))return;int2 q=int2((float2(p)+.5)*float2(src.get_width(),src.get_height())/float2(size));float xs[9],ys[9];int n=0;for(int j=-1;j<=1;j++)for(int i=-1;i<=1;i++){float2 a=src.read(uint2(clamp(q+int2(i,j),int2(0),int2(src.get_width()-1,src.get_height()-1)))).xy;xs[n]=a.x;ys[n]=a.y;n++;}for(int j=1;j<9;j++){float x=xs[j],y=ys[j];int k=j-1;while(k>=0&&xs[k]>x){xs[k+1]=xs[k];k--;}xs[k+1]=x;k=j-1;while(k>=0&&ys[k]>y){ys[k+1]=ys[k];k--;}ys[k+1]=y;}float2 v=float2(xs[4],ys[4])*float2(size)/float2(src.get_width(),src.get_height());dst.write(half4(half2(v),0,0),p);}";
        NSError *error=nil;id<MTLLibrary> lib=[g_dev newLibraryWithSource:source options:nil error:&error];
        if(!lib)MDIE("MetalFX motion shaders: %s",error.localizedDescription.UTF8String);
        reduce=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"reduceGray"] error:&error];
        search=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"matchFlow"] error:&error];
        expand=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"expandFlow"] error:&error];
        if(!reduce||!search||!expand)MDIE("MetalFX motion pipelines failed");
        // Keep the scalar reduction pipeline with the color reduction pipeline.
        scalar=[g_dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"reduceOne"] error:&error];if(!scalar)MDIE("MetalFX scalar pipeline failed");
    }
    if(width!=current.width||height!=current.height){
        width=current.width;height=current.height;
        for(int level=0;level<4;level++){
            NSUInteger w=MAX(1,(width+((1<<(level+2))-1))>>(level+2)),h=MAX(1,(height+((1<<(level+2))-1))>>(level+2));
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR16Float width:w height:h mipmapped:NO];d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
            for(int i=0;i<2;i++){gray[i][level]=[g_dev newTextureWithDescriptor:d];if(!gray[i][level])MDIE("MetalFX gray allocation");}
            d.pixelFormat=MTLPixelFormatRG16Float;flow[level]=[g_dev newTextureWithDescriptor:d];if(!flow[level])MDIE("MetalFX motion allocation");
        }
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRG16Float width:width height:height mipmapped:NO];d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;motion=[g_dev newTextureWithDescriptor:d];if(!motion)MDIE("MetalFX dense motion allocation");
    }
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    for(int i=0;i<2;i++)for(int level=0;level<4;level++){
        id<MTLTexture> dst=gray[i][level];[enc setComputePipelineState:level?scalar:reduce];
        [enc setTexture:level?gray[i][level-1]:(i?previous:current) atIndex:0];[enc setTexture:dst atIndex:1];
        [enc dispatchThreads:MTLSizeMake(dst.width,dst.height,1) threadsPerThreadgroup:MTLSizeMake(16,8,1)];
        [enc memoryBarrierWithScope:MTLBarrierScopeTextures];
    }
    for(int level=3;level>=0;level--){uint32_t first=level==3;id<MTLTexture> dst=flow[level];
        [enc setComputePipelineState:search];[enc setTexture:gray[0][level] atIndex:0];[enc setTexture:gray[1][level] atIndex:1];[enc setTexture:first?gray[0][level]:flow[level+1] atIndex:2];[enc setTexture:dst atIndex:3];[enc setBytes:&first length:4 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(dst.width,dst.height,1) threadsPerThreadgroup:MTLSizeMake(16,8,1)];[enc memoryBarrierWithScope:MTLBarrierScopeTextures];
    }
    [enc setComputePipelineState:expand];[enc setTexture:flow[0] atIndex:0];[enc setTexture:motion atIndex:1];[enc dispatchThreads:MTLSizeMake(width,height,1) threadsPerThreadgroup:MTLSizeMake(16,8,1)];[enc endEncoding];
    return motion;
}
