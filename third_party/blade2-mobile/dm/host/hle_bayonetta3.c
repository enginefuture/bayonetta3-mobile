// Bayonetta 3 service adapters, isolated from the upstream game's fixed addresses.
#include "hle.h"
#if DM_BAYONETTA3
#include <stdatomic.h>
// oe::MuteRecording/UnmuteRecording control audio in the platform's captured
// clips, not AudioOut. The host exposes no Horizon clip recorder (see oe's
// Enable/DisableRecording adapters). Keep this policy locally and never enter
// the uninitialized SDK recording-service singleton or mute game playback.
static _Atomic int bayo_recording_muted;
HLE_FORCE("_ZN2nn2oe13MuteRecordingEv", "宿主无系统录像；记录录像静音策略，游戏声音不变", void,
          h_bayo_MuteRecording, void) {
    atomic_store_explicit(&bayo_recording_muted,1,memory_order_relaxed);
    LOG("[recording-policy] muted=1 recorder=unavailable playback=unchanged");
}
HLE_FORCE("_ZN2nn2oe15UnmuteRecordingEv", "宿主无系统录像；恢复录像声音策略，游戏声音不变", void,
          h_bayo_UnmuteRecording, void) {
    atomic_store_explicit(&bayo_recording_muted,0,memory_order_relaxed);
    LOG("[recording-policy] muted=0 recorder=unavailable playback=unchanged");
}
// Dedicated Switch USB keyboard/mouse devices are absent. The Mac keyboard is
// mapped to Npad by the host frontend. ABI extents verified from SDK 13 stores:
// KeyboardState [0,0x30); MouseState [0,0x28). Attributes stay disconnected.
HLE_FORCE("_ZN2nn3hid18InitializeKeyboardEv", "无独立 Switch USB 键盘；Mac 键盘映射到 Npad", void,
          h_bayo_InitKeyboard, void) { LOG("hid::InitializeKeyboard (disconnected)"); }
HLE_FORCE("_ZN2nn3hid15InitializeMouseEv", "无独立 Switch USB 鼠标", void,
          h_bayo_InitMouse, void) { LOG("hid::InitializeMouse (disconnected)"); }
HLE_FORCE("_ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE", "回报断开的 Switch 键盘状态", void,
          h_bayo_Keyboard, void *out) {
    if (!out) die("GetKeyboardState null output");
    memset(out,0,0x30); *(uint64_t *)out=guest_ns()/16666667;
}
HLE_FORCE("_ZN2nn3hid13GetMouseStateEPNS0_10MouseStateE", "回报断开的 Switch 鼠标状态", void,
          h_bayo_Mouse, void *out) {
    if (!out) die("GetMouseState null output");
    memset(out,0,0x28); *(uint64_t *)out=guest_ns()/16666667;
}
HLE_FORCE("_ZN2nn3hid21ShowControllerSupportERKNS0_20ControllerSupportArgE",
          "系统手柄选择器由宿主键盘、GameController 或触屏输入替代", Result,
          h_bayo_ControllerSupport, const void *arg) {
    (void)arg; LOG("hid::ShowControllerSupport (host input)"); return RES_OK;
}
HLE_FORCE("_ZN2nn6applet15SetCpuBoostModeEi", "宿主调度由 Apple 管理；记录 Switch 启动加速请求", void,
          h_bayo_CpuBoost, int mode) { LOG("applet::SetCpuBoostMode %d (host-managed)",mode); }
HLE_FORCE("_ZN2nn6applet18CancelCpuBoostModeEv", "撤销 Switch 启动加速请求；宿主调度由 Apple 管理", void,
          h_bayo_CancelBoost, void) { LOG("applet::CancelCpuBoostMode (host-managed)"); }
// SDK 13 LanguageCode is eight bytes, returned through x0's output pointer.
// Resolve the service-backed conversion locally; other settings IPC is untouched.
HLE_FORCE("_ZN2nn8settings6detail16MakeLanguageCodeEPNS0_12LanguageCodeENS0_8LanguageE",
          "本地语言枚举转换；不创建 Horizon settings 服务", Result,
          h_bayo_MakeLanguageCode, uint64_t *out, unsigned language) {
    static const char codes[][8] = {"ja","en-US","fr","de","it","es","zh-CN","ko","nl","pt","ru","zh-TW",
                                    "en-GB","fr-CA","es-419","zh-Hans","zh-Hant","pt-BR"};
    if (!out || language >= sizeof codes / sizeof *codes) die("MakeLanguageCode invalid language %u",language);
    memcpy(out,codes[language],8);
    return RES_OK;
}
// Host AudioOut is configured as stereo; this query must not initialize audren IPC.
HLE_FORCE("_ZN2nn5audio41GetActiveAudioDeviceChannelCountForOutputEv", "宿主立体声音频输出通道数", int,
          h_bayo_OutputChannels, void) { return 2; }
// AudioDeviceName is exactly 0x100 bytes in SDK 13 (IPC output descriptor).
static void bayo_audio_name(char *out){if(!out)die("AudioDeviceName null");memset(out,0,0x100);strcpy(out,"DeviceOut");}
HLE_FORCE("_ZN2nn5audio24GetActiveAudioDeviceNameEPNS0_15AudioDeviceNameE", "当前宿主音频设备", void,h_bayo_AudioName,char *out){bayo_audio_name(out);}
HLE_FORCE("_ZN2nn5audio30GetActiveAudioOutputDeviceNameEPNS0_15AudioDeviceNameE", "当前宿主输出设备", void,h_bayo_AudioOutputName,char *out){bayo_audio_name(out);}
HLE_FORCE("_ZN2nn5audio19ListAudioDeviceNameEPNS0_15AudioDeviceNameEi", "宿主音频设备列表", int,h_bayo_AudioNames,char *out,int n){if(n<1)return 0;bayo_audio_name(out);return 1;}
HLE_FORCE("_ZN2nn5audio25ListAudioOutputDeviceNameEPNS0_15AudioDeviceNameEi", "宿主输出设备列表", int,h_bayo_AudioOutputNames,char *out,int n){if(n<1)return 0;bayo_audio_name(out);return 1;}
HLE_FORCE("_ZN2nn5audio39AcquireAudioDeviceNotificationForOutputEPNS_2os11SystemEventE", "稳定的宿主立体声端点：有效、初始未触发的设备变更事件", Result,
 h_bayo_AudioOutputEvent,void *ev){static void *bound;if(bound)return 0x499;hle_bind_system_event(ev,0);bound=ev;return RES_OK;}
extern int touch_fill(void *,uint64_t);
HLE_FORCE("_ZN2nn3hid19GetTouchScreenStateILm16EEEvPNS0_16TouchScreenStateIXT_EEE", "单次触屏快照，委托宿主实际触点", void,
 h_bayo_TouchState,void *out){if(!out)die("TouchScreenState null");touch_fill(out,guest_ns());}
static _Atomic float bayo_device_volume=1.0f;
float dm_host_audio_device_gain(void){return atomic_load_explicit(&bayo_device_volume,memory_order_relaxed);}
HLE_FORCE("_ZN2nn5audio26SetAudioDeviceOutputVolumeEPKNS0_15AudioDeviceNameEf", "宿主 PCM 输出增益", void,h_bayo_DeviceVolume,const char *name,float value){
 if(!name || strcmp(name,"DeviceOut") || !(value>=0.0f && value<=1.0f))die("invalid host audio device volume");
 atomic_store_explicit(&bayo_device_volume,value,memory_order_relaxed);
}
HLE_FORCE("_ZN2nn5audio26GetAudioDeviceOutputVolumeEPKNS0_15AudioDeviceNameE", "宿主 PCM 输出增益查询", float,h_bayo_GetDeviceVolume,const char *name){if(!name || strcmp(name,"DeviceOut"))die("unknown host audio device");return dm_host_audio_device_gain();}
// PREPO is optional platform telemetry; this host has no Horizon report service.
HLE_FORCE("_ZN2nn5prepo10InitializeEv", "离线宿主无平台遥测服务", void,h_bayo_PreReportInit,void){LOG("prepo: platform report service unavailable");}
HLE_FORCE("_ZN2nn5prepo10PlayReport4SaveEv", "平台遥测存储不可用", Result,h_bayo_ReportSave,void *report){(void)report;return RES_FAIL;}
HLE_FORCE("_ZN2nn5prepo10PlayReport4SaveERKNS_7account3UidE", "平台遥测存储不可用", Result,h_bayo_ReportSaveUser,void *report,const void *uid){(void)report;(void)uid;return RES_FAIL;}
HLE_FORCE("_ZN2nn5prepo16SystemPlayReport4SaveEv", "系统遥测存储不可用", Result,h_bayo_SystemReportSave,void *report){(void)report;return RES_FAIL;}
HLE_FORCE("_ZN2nn5prepo16SystemPlayReport4SaveERKNS_7account3UidE", "系统遥测存储不可用", Result,h_bayo_SystemReportSaveUser,void *report,const void *uid){(void)report;(void)uid;return RES_FAIL;}
#endif
