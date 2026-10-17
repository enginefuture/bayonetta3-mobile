// Integration diagnostic: validate every actual vertex library against one
// fragment that consumes the complete scanned interface. Libraries stay private.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main(int argc,char **argv){@autoreleasepool{
 BOOL tess=argc==5&&!strcmp(argv[3],"--tess");
 if(argc!=3&&!tess)return 2;unsigned expected=(unsigned)strtoul(argv[2],NULL,10);
 NSString *root=@(argv[1]);NSError *error=nil;id<MTLDevice>d=MTLCreateSystemDefaultDevice();
 NSString *libraries=tess?@(argv[4]):root;
 NSDictionary *scan=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:@"_varying_scan.json"]] options:0 error:&error];
 NSString *hex=scan[@"components"];if(!hex||hex.length!=32)return 3;
 NSMutableString *source=[NSMutableString stringWithString:@"#include <metal_stdlib>\nusing namespace metal;\nstruct Inputs {\n"];
 NSMutableArray<NSNumber*> *locations=[NSMutableArray new];
 // A nonzero nibble means that at least one real fragment reads the location.
 for(int i=0;i<32;i++)if([hex characterAtIndex:31-i]!='0'){
  [locations addObject:@(i)];[source appendFormat:@"float4 v%d [[user(locn%d)]];\n",i,i];
 }
 [source appendString:@"};\nfragment float4 probe(Inputs in [[stage_in]]) { float4 s=float4(0);\n"];
 for(NSNumber*i in locations)[source appendFormat:@"s+=in.v%@;\n",i];
 [source appendString:@"return s; }\n"];
 id<MTLLibrary>fragment=[d newLibraryWithSource:source options:nil error:&error];
 if(!fragment){NSLog(@"probe fragment failed: %@",error);return 4;}
 id<MTLFunction>fs=[fragment newFunctionWithName:@"probe"];
 NSArray *names=[[[NSFileManager defaultManager] contentsOfDirectoryAtPath:libraries error:&error] sortedArrayUsingSelector:@selector(compare:)];
 unsigned passed=0;
 for(NSString*name in names){@autoreleasepool{
  if(![name hasSuffix:tess?@"_te.json":@"_b.json"]||[name hasPrefix:@"_"])continue;
  NSDictionary *meta=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[libraries stringByAppendingPathComponent:name]] options:0 error:&error];
  if(![meta[@"stage"] isEqual:tess?@"tes":@"vs"])continue;
  NSString*libname=[[name stringByDeletingPathExtension] stringByAppendingPathExtension:@"metallib"];
  id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[libraries stringByAppendingPathComponent:libname]] error:&error];
  id<MTLFunction>vs=[lib newFunctionWithName:meta[@"entry"]?:@"main0"];
  if(!vs){NSLog(@"vertex load failed %@: %@",name,error);return 5;}
  MTLRenderPipelineDescriptor*p=[MTLRenderPipelineDescriptor new];p.vertexFunction=vs;p.fragmentFunction=fs;
  p.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;p.depthAttachmentPixelFormat=MTLPixelFormatDepth32Float;p.inputPrimitiveTopology=MTLPrimitiveTopologyClassTriangle;
  NSString *msl=[NSString stringWithContentsOfFile:[libraries stringByAppendingPathComponent:[[name stringByDeletingPathExtension] stringByAppendingPathExtension:@"metal"]] encoding:NSUTF8StringEncoding error:&error];
  if([msl containsString:@"[[point_size]]"])p.inputPrimitiveTopology=MTLPrimitiveTopologyClassPoint;
  MTLVertexDescriptor*a=[MTLVertexDescriptor vertexDescriptor];NSUInteger offset=0;
  for(MTLVertexAttribute*x in vs.vertexAttributes){if(!x.active)continue;
   MTLVertexFormat fmt=x.attributeType==MTLDataTypeFloat4?MTLVertexFormatFloat4:x.attributeType==MTLDataTypeUInt4?MTLVertexFormatUInt4:x.attributeType==MTLDataTypeInt4?MTLVertexFormatInt4:MTLVertexFormatInvalid;
   if(fmt==MTLVertexFormatInvalid){NSLog(@"unknown vertex input %@ %@",name,x);return 6;}
   a.attributes[x.attributeIndex].format=fmt;a.attributes[x.attributeIndex].bufferIndex=30;a.attributes[x.attributeIndex].offset=offset;offset+=16;
  }
  a.layouts[30].stride=offset;p.vertexDescriptor=tess?nil:a;
  if(tess){p.maxTessellationFactor=64;p.tessellationPartitionMode=MTLTessellationPartitionModeInteger;p.tessellationFactorFormat=MTLTessellationFactorFormatHalf;p.tessellationControlPointIndexType=MTLTessellationControlPointIndexTypeNone;p.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionPerPatchAndPerInstance;p.tessellationOutputWindingOrder=MTLWindingCounterClockwise;}
  if(![d newRenderPipelineStateWithDescriptor:p error:&error]){NSLog(@"complete varying pipeline rejected %@: %@",name,error);return 1;}
  passed++;if(passed%250==0){printf("Validated %u vertex pipelines\n",passed);fflush(stdout);}
 }}
 printf("Complete varying interface: %u actual %s libraries passed real Metal pipeline creation (%lu locations)\n",passed,tess?"TES":"vertex",(unsigned long)locations.count);
 return passed==expected&&passed?0:7;
}}
