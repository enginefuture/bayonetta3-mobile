// Compile the actual adapters and protect caller memory with canaries.
#define DM_BAYONETTA3 1
#include "../third_party/blade2-mobile/dm/host/hle_bayonetta3.c"
#include "../third_party/blade2-mobile/dm/host/hle_account.c"
#include <assert.h>
void hle_bind_system_event(void *p,int clear){(void)p;(void)clear;}
int touch_fill(void *p,uint64_t t){(void)p;(void)t;abort();}
void hle_signal_system_event(void *p){(void)p;abort();}
uint64_t guest_ns(void) { return 1000000020ull; }
int main(void) {
    struct { uint64_t before; uint8_t state[0x30]; uint64_t after; } keyboard;
    struct { uint64_t before; uint8_t state[0x28]; uint64_t after; } mouse;
    memset(&keyboard,0xa5,sizeof keyboard); memset(&mouse,0xa5,sizeof mouse);
    h_bayo_Keyboard(keyboard.state); h_bayo_Mouse(mouse.state);
    assert(keyboard.before==0xa5a5a5a5a5a5a5a5ull && keyboard.after==keyboard.before);
    assert(mouse.before==0xa5a5a5a5a5a5a5a5ull && mouse.after==mouse.before);
    assert(*(uint64_t *)keyboard.state==60 && *(uint64_t *)mouse.state==60);
    for (size_t i=8;i<sizeof keyboard.state;i++) assert(keyboard.state[i]==0);
    for (size_t i=8;i<sizeof mouse.state;i++) assert(mouse.state[i]==0);
    struct { uint64_t before; uint64_t code; uint64_t after; } language={123,0,456};
    assert(h_bayo_MakeLanguageCode(&language.code,15)==0);
    assert(!memcmp(&language.code,"zh-Hans",8));
    assert(language.before==123 && language.after==456);
    struct { uint64_t before;char name[256];uint64_t after; } device;
    memset(&device,0xa5,sizeof device);h_bayo_AudioName(device.name);
    assert(device.before==0xa5a5a5a5a5a5a5a5ull && device.after==device.before && !strcmp(device.name,"DeviceOut"));
    assert(h_bayo_OutputChannels()==2);
    h_bayo_DeviceVolume("DeviceOut",0.25f);assert(h_bayo_GetDeviceVolume("DeviceOut")==0.25f && dm_host_audio_device_gain()==0.25f);
    int count=-1;struct {uint64_t before;UserHandle h;uint64_t after;} user={.before=123,.after=456};
    h_bayo_PopUsers(&count,&user.h,1);assert(count==0);h_bayo_PushUsers();Uid uid;
    assert(h_bayo_ListPushed(&uid,1)==1 && !memcmp(&uid,&k_uid,sizeof uid));
    h_bayo_PopUsers(&count,&user.h,1);assert(count==1 && user.h.v[2]==HANDLE_MAGIC && user.before==123 && user.after==456);
    assert(h_bayo_ListPushed(&uid,1)==0);
    puts("SDK adapter buffer/ABI tests passed");
}
