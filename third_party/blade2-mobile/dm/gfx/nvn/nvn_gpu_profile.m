#import "nvn_gpu_profile.h"
#include <mach/mach_time.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>

enum { GP_ALLOCATORS=8, GP_ENTRIES=4096, GP_PASSES=GP_ENTRIES/2 };
typedef struct { uint64_t frame,submission; uint32_t index,width,height; char kind; } gp_row;
static id<MTL4CounterHeap> heaps[GP_ALLOCATORS];
static gp_row rows[GP_PASSES];
static unsigned current_slot,nrows;
static int open_row=-1,enabled=-1;
static __unsafe_unretained id open_encoder;
static FILE *output;
static unsigned every=60;
static uint64_t byte_count,byte_limit=32*1048576;
static int busy[GP_ALLOCATORS];
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready=PTHREAD_COND_INITIALIZER;
static double tick_ns;
static uint64_t submission;
static _Atomic int stopped;

void dm_gpu_profile_submit(id<MTLDevice> device,unsigned slot) {
    if(enabled<0){
        const char *path=getenv("DM_GPU_PASS_PROFILE");enabled=path && *path;
        if(!enabled)return;
        const char *stride=getenv("DM_GPU_PASS_EVERY");if(stride){long n=strtol(stride,NULL,10);if(n>0 && n<=3600)every=(unsigned)n;}
        output=fopen(path,"w");
        if(!output){fprintf(stderr,"[dm] FATAL cannot open GPU pass profile\n");abort();}
        mach_timebase_info_data_t tb;mach_timebase_info(&tb);tick_ns=(double)tb.numer/tb.denom;
        fprintf(output,"# Metal4 precise timestamp probes; may split encoders and inflate timing; spans cannot be summed as independent work\nframe\tsubmission\tindex\tkind\twidth\theight\tspan_ms\tbegin_ticks\tend_ticks\n");
        fprintf(stderr,"[dm] [gpu-profile] Metal4 precise probes every=%u; diagnostic timing only\n",every);
    }
    if(!enabled || atomic_load(&stopped))return;
    if(slot>=GP_ALLOCATORS){fprintf(stderr,"[dm] FATAL GPU profile allocator slot\n");abort();}
    pthread_mutex_lock(&lock);
    while(busy[slot])pthread_cond_wait(&ready,&lock);
    pthread_mutex_unlock(&lock);
    if(!heaps[slot]){
        MTL4CounterHeapDescriptor *d=[MTL4CounterHeapDescriptor new];d.type=MTL4CounterHeapTypeTimestamp;d.count=GP_ENTRIES;
        NSError *error=nil;heaps[slot]=[device newCounterHeapWithDescriptor:d error:&error];
        if(!heaps[slot]){fprintf(stderr,"[dm] FATAL GPU profile counter heap: %s\n",error.description.UTF8String);abort();}
    }
    [heaps[slot] invalidateCounterRange:NSMakeRange(0,GP_ENTRIES)];
    current_slot=slot;nrows=0;open_row=-1;open_encoder=nil;submission++;
}

static void timestamp(id encoder,char kind,unsigned index){
    if(kind=='R')[(id<MTL4RenderCommandEncoder>)encoder writeTimestampWithGranularity:MTL4TimestampGranularityPrecise afterStage:MTLRenderStageFragment intoHeap:heaps[current_slot] atIndex:index];
    else [(id<MTL4ComputeCommandEncoder>)encoder writeTimestampWithGranularity:MTL4TimestampGranularityPrecise intoHeap:heaps[current_slot] atIndex:index];
}

void dm_gpu_profile_begin(id encoder,char kind,uint64_t frame,unsigned width,unsigned height){
    if(enabled!=1 || atomic_load(&stopped) || frame%every)return;
    if(nrows==GP_PASSES){fprintf(stderr,"[dm] [gpu-profile] counter_limit frame=%llu; partial sample\n",(unsigned long long)frame);return;}
    if(open_row>=0){fprintf(stderr,"[dm] FATAL nested GPU profile encoder\n");abort();}
    gp_row *r=&rows[nrows];*r=(gp_row){frame,submission,nrows,width,height,kind};
    open_row=(int)nrows++;open_encoder=encoder;
    timestamp(encoder,kind,(unsigned)open_row*2);
}

void dm_gpu_profile_end(id encoder){
    if(open_row<0 || encoder!=open_encoder)return;
    timestamp(encoder,rows[open_row].kind,(unsigned)open_row*2+1);
    open_row=-1;open_encoder=nil;
}

dispatch_block_t dm_gpu_profile_seal(void){
    if(enabled!=1 || !nrows)return nil;
    if(open_row>=0){fprintf(stderr,"[dm] FATAL unclosed GPU profile encoder\n");abort();}
    unsigned count=nrows,slot=current_slot;
    gp_row *copy=malloc(count*sizeof *copy);if(!copy)abort();memcpy(copy,rows,count*sizeof *copy);
    id<MTL4CounterHeap> heap=heaps[slot];
    pthread_mutex_lock(&lock);busy[slot]=1;pthread_mutex_unlock(&lock);
    nrows=0;
    return ^{
        NSData *data=[heap resolveCounterRange:NSMakeRange(0,count*2)];
        pthread_mutex_lock(&lock);
        if(!data || data.length<count*2*sizeof(MTL4TimestampHeapEntry)){
            fprintf(stderr,"[dm] [gpu-profile] counter_resolve_failed slot=%u; no sample\n",slot);
        }else if(output){
            const MTL4TimestampHeapEntry *ts=data.bytes;
            for(unsigned i=0;i<count;i++){
                uint64_t a=ts[i*2].timestamp,b=ts[i*2+1].timestamp;
                // A clear-only/empty render pass may have no fragment timestamp.
                // Keep the missing observation visible; never turn it into zero cost.
                double span=(!a||b<a)?-1.0:(b-a)*tick_ns/1e6;
                int bytes=fprintf(output,"%llu\t%llu\t%u\t%c\t%u\t%u\t%.6f\t%llu\t%llu\n",(unsigned long long)copy[i].frame,(unsigned long long)copy[i].submission,copy[i].index,copy[i].kind,copy[i].width,copy[i].height,span,(unsigned long long)a,(unsigned long long)b);
                if(bytes>0)byte_count+=(unsigned)bytes;
                if(byte_count>=byte_limit){fprintf(stderr,"[dm] [gpu-profile] file_limit_reached; collection stopped\n");fclose(output);output=NULL;atomic_store(&stopped,1);break;}
            }
            if(output)fflush(output);
        }
        busy[slot]=0;pthread_cond_broadcast(&ready);pthread_mutex_unlock(&lock);
        free(copy);
    };
}
