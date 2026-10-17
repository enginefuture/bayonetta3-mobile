#pragma once
#include <stdint.h>
#include <string.h>
// NVN 55 / GPU code 1.15 uses a 0x850-byte control block. Its declared
// size is at +0x20; legacy games retain their original 0x880 hashing contract.
static inline uint32_t nvn_control_size(const void *control){
#if DM_BAYONETTA3
    const uint8_t *p=control;uint32_t magic,major,minor,size;
    memcpy(&magic,p,4);memcpy(&major,p+4,4);memcpy(&minor,p+8,4);memcpy(&size,p+0x20,4);
    return magic==0x98761234 && major==1 && ((minor==12 && size==0x838) || (minor==14 && size==0x848) || (minor==15 && size==0x850) || (minor==16 && size==0x880))?size:0;
#else
    (void)control;return 0x880;
#endif
}
