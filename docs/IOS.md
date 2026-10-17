# iOS device port / iOS 真机移植

This is a native compatibility-layer development build. You must own the game and prepare your own verified Bayonetta 3 1.2.0 files. The repository provides no NSP, keys, game shaders or game assets. Local App/IPA builds embed your rewritten game programs and shaders; keep them private.

这是原生兼容层开发构建。请支持正版，自行准备已核验的 Bayonetta 3 1.2.0 文件。仓库不提供 NSP、密钥、游戏着色器或素材。本机 App/IPA 包含你的游戏改写程序及着色器，不可随源码发布。

## Supported and tested / 支持与实测范围

| Item / 项目 | Status / 状态 |
|---|---|
| Tested phone / 实测手机 | iPhone Air, Apple A19 Pro GPU, iOS 27.2; native 2736×1260 landscape / 原生横屏 |
| Actual execution / 实际运行 | Development-signed installation, menus and real combat; user-confirmed sound, full-screen wide view and normal HUD / 已签名安装、菜单和真实战斗，声音/真宽屏/HUD 经用户确认 |
| Minimum build target / 工程最低目标 | iOS 26.0, Metal 4; this is not proof that every iOS 26 device can run the game / 不代表所有 iOS 26 设备均可运行 |
| Signing / 签名 | Your own development team, Increased Memory Limit and Extended Virtual Addressing / 自己的开发团队及两项内存权限 |
| Other devices / 其他设备 | Other iPhone models and iPads are unverified; no simulator gameplay support / 其他 iPhone、iPad 未验收，不支持模拟器游戏运行 |
| Remaining limits / 限制 | Heavy-effect frame drops; full chapters, sustained thermal behavior and all lifecycle/cutscene paths remain unverified / 大量特效掉帧，完整章节、持续温控和全部生命周期/过场路径待验收 |

## Startup settings / 启动设置

The existing Bayonetta 3 app opens a native settings page before creating a Metal device or loading the guest. The layout follows the Play-plus-settings flow in the local Mush8 launcher. Choose **Normal / Wide**, toggle **Metal HUD** and **MetalFX**, then tap **Play**. Choices save locally and apply to that launch; reopen the app to change them. First-use defaults are Wide, HUD off and MetalFX on. There is one installed app and one bundle identifier. Upgrading the same bundle preserves the private resources and existing save; do not uninstall the game app when updating.

原来的 Bayonetta 3 App 启动时先显示原生设置页，参考 Mush8 的“开始游戏＋设置”流程。选择 **正常／宽屏**，独立开关 **Metal HUD**、**MetalFX 超分**，再点击 **开始游戏**。选择会自动保存，在本次启动生效；再次打开可修改。首次默认宽屏、HUD 关闭、MetalFX 开启。只有一个 App；使用相同包名覆盖升级保留自有资源和存档，更新时不要先卸载游戏 App。

Both Normal and Wide programs are embedded as separate immutable signed sections in the same executable. The loader selects the matching main image before preload; no runtime code-page patching is used. Settings cannot change only an output getter and leave the camera or targets mismatched. The private build receipt records the original and configured image hashes. The test runner used during development was removed; no separate launcher/test app is required or shipped.

正常和宽屏映像以两个只读签名版本放在同一可执行文件里，在预装载前选择；不在真机运行时改写代码页。渲染目标、相机、HUD 与输出尺寸保持一致。开发期间的测试程序已删除，不需要也不发布第二个启动器或测试 App。

## Graphics policy / 图形策略

- **Normal:** the original handheld picture and matching DRS/depth/HDR/AO allocations. On the tested phone, the active 1280×720 area is cropped from its original allocation. With MetalFX enabled it scales to 2240×1260, retaining 16:9 side margins.
- **Wide:** the exact-build 1568×720 profile synchronizes render targets, all preinitialized DRS alias limits, primary-camera and logical HUD dimensions. It expands horizontal FOV while preserving vertical FOV and authored UI aspect compensation. MetalFX output is 2736×1256, presented across the 2736×1260 display; the existing presentation layer absorbs the roughly 0.29% alignment remainder.
- **MetalFX off:** normal presentation scales the selected mode to fit the native drawable without the MetalFX pass. Disabling super-resolution does not switch the camera mode.
- **Metal HUD:** the launch switch controls the system performance overlay before first Metal-device creation. Device timing logs remain independent of this visible overlay.
- **Frame generation:** disabled on iOS. Neither mode allocates Mac fixed 3840×2160 outputs. Output-slot resizing waits for GPU completion; unsupported upscale configurations fall back to ordinary presentation.
- **Input/lifecycle:** physical-controller and touch input adapters are included. Foreground/background paths release input and suspend/resume audio, the guest clock and GPU; complete interruption/accessory coverage is not yet established.

正常模式保留原版 16:9，超宽手机两侧留边。宽屏模式扩大左右视野，同步离屏目标和 HUD；该配置针对实测的 2736×1260 横屏，其他比例和辅助/过场相机需分别验证。关闭 MetalFX 后仍按所选模式显示，只跳过超分。Metal HUD 开关控制可见的性能叠层，不影响独立诊断日志。手机不使用 Mac 固定 4K，也不启用帧生成。

AudioOut and AudioRenderer both establish `AVAudioSessionCategoryPlayback` before RemoteIO creation. Foreground/background and system interruptions control both output paths. The connected-device user confirmed restored music and effects. The log reports the actual route, hardware buffer duration and volume. / 已修复游戏实际使用的 AudioOut 未初始化 Playback 会话导致静音的问题；前后台和系统打断统一管理两条音频路径。用户已确认声音恢复，实际线路、缓冲时长及音量写入日志。

## Build and install / 构建与安装

First complete the exact-version extraction/rewrite verification, media preparation and full Mac shader build described in [BUILD.md](BUILD.md) / [中文教程](BUILD.zh-CN.md). The mobile builders require the current checksummed complete corpus, including the Mac tessellation supplement.

```sh
.venv/bin/python tools/build_ios_shaders.py --jobs 6
.venv/bin/python tools/build_ios_tessellation.py
xcrun devicectl list devices
.venv/bin/python tools/build_ios.py --sign --team-id YOUR_TEAM_ID \
  --bundle-id YOUR_UNIQUE_BUNDLE_ID --device YOUR_DEVICE_UDID
```

The standard builder now includes **both** launch modes; `--widescreen` is retained only for command-line compatibility and is no longer required. Local LLVM (`/opt/homebrew/opt/llvm/bin/llvm-mc`) and Unicorn independently verify instructions, actual DRS paths and camera math before creating the private configured copy. Exact original Build ID/hash and per-word guards remain enforced. The original `work/rewrite/` stays unchanged. The signed bundle records `dm/mobile-graphics.json`; all generated programs, libraries and receipts stay private.

现在标准构建即包含正常和宽屏两种启动选项，无需 `--widescreen`（旧参数仅为兼容保留）。构建前执行 LLVM/Unicorn 校验，原始改写目录保持不变；所有生成程序、着色器和私有回执均不随源码上传。

Use an unlocked physical iOS 26+ device and an Xcode account capable of provisioning Increased Memory Limit and Extended Virtual Addressing. Valid local signing certificates alone do not create the required app-specific provisioning profile. Release is the default. Inspect `work/build-ios.log`; the build command does not install or publish anything.

使用已解锁的 iOS 26+ 真机，Xcode 登录自己的开发团队，并确认包名对应的描述文件允许增加内存上限及扩展虚拟地址。只有证书而未登录 Xcode，通常无法为新包名申请这些权限。默认构建 Release；日志为 `work/build-ios.log`，构建命令不会上传或发布。

```sh
xcrun devicectl device install app --device YOUR_DEVICE_UDID \
  work/ios/Build/Products/Release-iphoneos/Bayonetta3.app
# First launch creates the transfer directories and shows the asset instructions.
xcrun devicectl device process launch --device YOUR_DEVICE_UDID YOUR_UNIQUE_BUNDLE_ID
xcrun devicectl device copy to --device YOUR_DEVICE_UDID \
  --domain-type appDataContainer --domain-identifier YOUR_UNIQUE_BUNDLE_ID \
  --source work/game/RomFS --destination 'Library/Application Support/romfs'
xcrun devicectl device copy to --device YOUR_DEVICE_UDID \
  --domain-type appDataContainer --domain-identifier YOUR_UNIQUE_BUNDLE_ID \
  --source work/media --destination Documents/media
xcrun devicectl device process launch --device YOUR_DEVICE_UDID \
  --terminate-existing YOUR_UNIQUE_BUNDLE_ID
```

For unreliable or interrupted connections, use the resumable transfer helper instead of the two folder-copy commands:

```sh
.venv/bin/python tools/transfer_ios_assets.py --device YOUR_DEVICE_UDID \
  --bundle-id YOUR_UNIQUE_BUNDLE_ID
```

It skips matching file lengths, copies sequentially with three retries per file, and checks the final remote inventory. Its private journal lives in `work/ios-device/`. It does not touch saves. / 连接不稳定时建议用上述续传工具，按文件复制、重试并核对完整长度；不会覆盖存档。

Keep device operations sequential. Transfer the entire RomFS and prepared movie cache; the game cannot run from `core_000.pkz` alone. The private bundle records required file names/lengths and refuses to enter the guest while copying is incomplete. This length check detects incomplete transfers; it is not a new cryptographic validation of game contents. Saves live independently in `Documents/save`; do not overwrite an existing device save while transferring assets.

依次执行设备操作，完整复制 RomFS 和转换影片缓存；只有 `core_000.pkz` 不能运行。App 根据私有清单检查所有必需文件及长度，复制未完成时显示说明，不进入游戏。该检查不替代原始版本和内容哈希核验。手机存档位于 `Documents/save`，传资源时勿覆盖已有进度。

## Observed device result / 真机结果

On the connected iPhone Air, the development-signed expanded-FOV build enters actual combat; the user confirmed full-screen rendering and normal HUD. Music/effects were also confirmed after the AudioOut session fix. The latest in-place upgrade exposes all three launch settings; normal mode with both switches off and wide mode with MetalFX on have matching image-selection/crop logs. The user subsequently reported that the current version works normally. Effect-heavy performance still needs optimization; this does not establish every chapter, cutscene or device. / 已在连接的 iPhone Air 进入真实战斗，用户确认全屏及 HUD 正常，音频修复也已确认。最新覆盖升级已显示三个启动选项；正常模式＋两个开关关闭、宽屏＋MetalFX 开启的日志与对应映像/裁切一致，用户随后反馈当前均正常。大量特效场景帧率仍需优化，其他章节、过场和设备尚未全部验收。

## Diagnostics and acceptance / 日志与验收

Files in the app's Documents directory:

| File | Meaning / 用途 |
|---|---|
| `boot.txt`, `boot.previous.txt` | Current/previous startup, service/shader/GPU errors / 当前与上次启动日志 |
| `device-report.json` | OS, actual GPU, memory budget, BC texture and MetalFX support / 实际设备能力 |
| `frames.tsv` | Bounded per-frame timings; independent of the Mac HUD / 有上限的逐帧性能日志 |
| `save/` | Device-local progress / 真机独立存档 |

```sh
xcrun devicectl device copy from --device YOUR_DEVICE_UDID \
  --domain-type appDataContainer --domain-identifier YOUR_UNIQUE_BUNDLE_ID \
  --source Documents/boot.txt --destination work/ios-boot.txt
```

Thermal state changes and low-memory warnings are recorded in the boot log. Check actual MetalFX input/output sizes, first rendered frames, title input, gameplay, scene transitions, audio and suspend/resume separately. Host GPU tests, successful signing and installation do not establish iPhone gameplay or a frame-rate claim. See [STATUS.md](STATUS.md) for observed results.
