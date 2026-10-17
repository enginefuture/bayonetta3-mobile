#pragma once
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdint.h>
// Optional Metal 4 diagnostic. Caller serializes encoding; completion is on the
// GPU queue's feedback path. Precise probes affect timing: not an FPS benchmark.
void dm_gpu_profile_submit(id<MTLDevice> device, unsigned allocator_slot);
void dm_gpu_profile_begin(id encoder, char kind, uint64_t frame, unsigned width, unsigned height);
void dm_gpu_profile_end(id encoder);
dispatch_block_t dm_gpu_profile_seal(void);
