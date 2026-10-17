// Integration diagnostic: real translated libraries required; no game data included.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=3)return 2;id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSError*e=nil;

 id<MTLLibrary>v=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&e];
 id<MTLLibrary>f=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[2])] error:&e];
 if(!v||!f){NSLog(@"library error %@",e);return 3;}
 MTLRenderPipelineDescriptor*p=[MTLRenderPipelineDescriptor new];p.vertexFunction=[v newFunctionWithName:@"main0"];p.fragmentFunction=[f newFunctionWithName:@"main0"];p.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;p.depthAttachmentPixelFormat=MTLPixelFormatDepth32Float;
 MTLVertexDescriptor*a=[MTLVertexDescriptor vertexDescriptor];int off=0;
 for(MTLVertexAttribute*x in p.vertexFunction.vertexAttributes){if(!x.active)continue;if(x.attributeType!=MTLDataTypeFloat4){NSLog(@"unhandled actual attribute %@",x);return 4;}a.attributes[x.attributeIndex].format=MTLVertexFormatFloat4;a.attributes[x.attributeIndex].bufferIndex=30;a.attributes[x.attributeIndex].offset=off;off+=16;}
 a.layouts[30].stride=off;p.vertexDescriptor=a;id<MTLRenderPipelineState>ps=[d newRenderPipelineStateWithDescriptor:p error:&e];
 if(!ps){NSLog(@"PAIR REJECTED %@",e);return 1;}puts("Actual VS/FS interface pipeline creation passed");return 0;
}}
