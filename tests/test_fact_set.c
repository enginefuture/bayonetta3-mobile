#include <assert.h>
#include <stdio.h>
#include "../third_party/blade2-mobile/dm/gfx/nvn/nvn_fact_set.h"
int main(void) {
    nvn_hmap seen={0};
    assert(!nvn_fact_seen(&seen,"0000000000000000",0,0));
    assert(nvn_fact_seen(&seen,"0000000000000000",0,0));
    assert(!nvn_fact_seen(&seen,"0000000000000000",0,3));
    assert(nvn_fact_seen(&seen,"0000000000000000",0,0));
    assert(!nvn_fact_seen(&seen,"0000000000000000",1,0));
    assert(!nvn_fact_seen(&seen,"0000000000000001",0,0));
    for(unsigned i=2;i<10000;i++)assert(!nvn_fact_seen(&seen,"0000000000000000",i,0));
    for(unsigned i=2;i<10000;i++)assert(nvn_fact_seen(&seen,"0000000000000000",i,0));
    puts("Fact dedup: shader/slot/type isolation, type return and growth passed");
    return 0;
}
