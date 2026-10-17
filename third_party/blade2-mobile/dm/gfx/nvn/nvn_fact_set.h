// Shader interface observation deduplication; synthetic identity, no game data.
#pragma once
#include "nvn_hmap.h"
// Caller serializes access. Full shader key/slot/type: no per-observation allocation
// on the repeated path, no conflation when a slot changes type and changes back.
static inline int nvn_fact_seen(nvn_hmap *seen, const char *shader, uint32_t slot, uint32_t type) {
    struct { char shader[16]; uint32_t slot, type; } key = {0};
    memcpy(key.shader, shader, sizeof key.shader); key.slot = slot; key.type = type;
    if (!seen->klen) nvn_hm_init(seen, sizeof key);
    if (nvn_hm_get(seen, &key)) return 1;
    nvn_hm_put(seen, &key, (void *)(uintptr_t)1);
    return 0;
}
