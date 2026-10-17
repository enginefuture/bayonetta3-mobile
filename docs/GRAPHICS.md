# Graphics experiments / 图形实验

The previously failing scene now executes original three-control-point NVN tessellation (`TCS=5c35421616074e20`, `TES=6d536748a931bb27`). The user confirmed entry and normal visuals with fixed 1080p, MetalFX spatial 4K and HUD enabled. This validates the observed continuation, not all tessellation programs or chapters.

此前退出点现已执行原始细分阶段；用户确认进入新场景且画面正常。固定 1080p、MetalFX spatial 4K 和 HUD 均开启。已通过当前续玩路径，完整关卡和所有细分程序仍待验证。

## Native tessellation / 原生曲面细分

The pinned translator decodes original TCS/TES captures into SPIR-V. Guarded SPIRV-Cross lowering gives VS/TCS/TES a common 528-byte control-point layout, retaining original calculations and resource bindings. VS executes as an indexed/instanced compute capture, TCS writes control points and half-precision triangle factors, and Metal's fixed-function tessellator invokes the original TES as a post-tessellation vertex function. TES exports the same complete varying interface as ordinary vertices.

Metal 4 exposes no patch draw in the tested SDK. A synchronized Metal 3 command-buffer island performs tessellation between Metal 4 submissions, with shared-event ordering and checked completion. It retains real indices, base vertex, base instance, per-instance vertex divisors, attachment views, depth/stencil, alpha/depth-bounds rejection and fragment bindings. Per-draw CPU completion waits favor correctness and may need batching if later scenes submit many patches. The ordinary GPU timing counter does not include this island; separate `[tessellation]` samples report its command-buffer GPU time.

原始着色器离线翻译后，VS 计算捕获顶点，TCS 生成控制点和细分因子，Metal 硬件细分器调用 TES；不是跳过 patch 或直接当普通三角形绘制。当前验证三控制点、三角域、整数分割和 CCW 的已采集配置。补充库独立校验工具源码、普通缓存链、原始采集哈希和全部产物，正常启动拒绝过期/损坏/缺失库。生成的 MSL、库和原始着色器只存 `work/`。

```sh
# After capturing an actual VS/TCS/TES combination with the local native host:
.venv/bin/python tools/build_tessellation.py
make mac
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud --profile
.venv/bin/python tests/run_tessellation.py
```

Current coverage: one observed VS/TCS/TES combination executed in-game; all five captured TCS, six TES and 25 candidate VS compute variants compile. The two TES (`17f64cbfcdb0f91f`, `a2d16cf672285e87`) now use guarded SPIR-V input lowering and physical lane reconstruction from ballot/prefix operations, preserving original loads/shuffles and calculations. All six pass actual Metal pipeline creation. Non-contiguous subgroup masks and actual post-tessellation shuffles pass GPU checks. Unknown VS variants, vertex-ID-dependent indexed VS, non-triangle domains, other patch sizes/partition modes, cross-invocation TCS barriers, indirect patch arguments and attachmentless patch draws remain unsupported. A successful compile of an unused stage is not gameplay evidence.

6 组无游戏资源的真实 GPU 测试在 Metal API validation 下回读颜色/深度：32/16 位索引与 base vertex、数组 first vertex、非零 base instance 的两实例、divisor=2 的四实例属性、普通非实例化命令、空 scissor；TES 的曲面位移必须改变实际深度。实例属性按 `base + floor(localInstance/divisor)` 取址，并以独立普通 Metal 顶点管线核对。两份 subgroup TES 已实现并经独立 GPU 检查；更多实际阶段组合仍是后续兼容工作，不能保证任意新场景均通过。

## Packaged texture layout / 预排布纹理布局

The results-screen magenta blocks were invalid ASTC blocks caused by addressing, not replacement art. Packaged layout byte 1 specifies an additional horizontal GOB alignment. For the observed 1024/1026 ASTC 6×6 assets, 171 blocks occupy 43 dense GOB columns but the stored rows use 48. Ignoring the alignment reads zero padding as ASTC data and shifts later tile rows; the independent Arm decoder found 2,183 invalid blocks in one original capture. Using the packaged width alignment reduces this to zero. Mip offsets and the total storage extent must use the same rule; smaller mips that no longer contain a full sparse tile return to dense row addressing, following the existing deko3d layout model.

当前修正覆盖 CPU 解排布、Metal 3/4 GPU 解排布、mip 起点/总尺寸及纹理区域写入，并保持 `nvn_texdesc` 36 字节布局。未指定横向对齐的纹理维持原结果。新增无游戏资源的 ASTC 常量块 fixture，独立构造 48/32/11 GOB 行布局，实际回读 1024/1026 边缘、三级 mip、区域写入和生产 Metal 4 上传；旧寻址负对照必须重现 2,183 块错误。真实采集中六张受影响纹理原有的大块纯紫色消失，修复版再次采集的四张纹理全部 mip 经独立解码均无无效块（其中一张十级 mip）。

The user confirmed the same results screen: magenta blocks disappeared and smoke returned to normal. The accepted run used fixed 1080p, spatial 4K and HUD, and exited normally after 198.83 seconds. This does not verify every material or every source of terrain/transparency noise.

For local debugging, launch with `--inspect-frame N` to prepare a private output directory. The debugger-only `dm_gfx_inspect_next(1)` entry point arms one subsequent frame, recording draw bindings and bounded original/uploaded ASTC samples (at most 64 textures / 64 MiB of source data). Diagnostics are inactive in normal launches. All captured data remain under ignored `work/`; the reference decoder is a local analysis tool, not a runtime dependency.

```sh
.venv/bin/python tests/run_texture_layout.py
```

## Fixed 1080p and spatial 4K / 固定 1080p 与 4K 超分

`tools/graphics_profile.py` requires the exact original main NSO identity and unchanged verified rewrite. It creates a private launch copy, validates every changed original instruction/table, records hashes and preserves the verified source image. Configuration is intentional graphics policy, not equivalence to original resolution. It pins both DRS selectors to bank zero and updates that bank's depth/HDR/AO sizes and the scene/output dimensions together. Other banks retain original constants; half/quarter-resolution effects keep their relative sizes.

原方案只扩大深度分辨率表，未同步所有 HDR/AO 创建常量；用户对照确认 900p 不闪而 1080p 关闭 MetalFX 仍闪。现固定同一 DRS 档并同步尺寸，实际帧日志确认 1920×1080 主目标和 960×540 半分辨率目标。36 处指令经过 LLVM 独立解码、实际选择函数经过 Unicorn 1,024 组设置检查，另有原字节保护、变化范围、寄存器和 flags 测试。用户确认修复版当前新场景画面正常；长期闪黑专项复测和更多场景仍待验证。

MetalFX spatial uses the public MetalFX encoder with perceptual scan-out colors and a GPU shared-event bridge into the Metal 4 renderer. Three outputs are reused after GPU completion. The output canvas is 3840×2160; its physical display resolution depends on the connected screen. The spatial GPU test checks 1080p → 4K gray levels and repeated output-slot reuse with Metal validation enabled.

```sh
# Default experimental graphics profile; interpolation remains OFF.
.venv/bin/python tools/run_mac.py --seconds 0 --profile
# Original-resolution comparison.
.venv/bin/python tools/run_mac.py --seconds 0 --render-resolution native --metalfx off
# Same-frame source/output luminance diagnostics, private under work/.
.venv/bin/python tools/run_mac.py --seconds 0 --profile --diagnostic-luminance
.venv/bin/python tools/verify_graphics_profile.py
```

## Window, HUD and icon / 窗口、HUD 与图标

Use the window's Full Screen button, its green system button, or Control-Command-F. The title-bar HUD button and View menu toggle the native overlay; Shift-Command-H also works. The setting is saved locally. Game FPS counts original game frames; Display FPS counts actual presentation callbacks, including generated frames when enabled. Game GPU timing does not include all upscale/interpolation work. Apple's separate Metal Performance HUD can be enabled at startup with `--metal-hud`; the application overlay has its own reliable runtime toggle.

全屏可使用标题栏按钮、系统绿色按钮或 ⌃⌘F。标题栏 HUD 按钮、View 菜单和 ⇧⌘H 可以随时开关程序自身的性能浮层，并保存选择。Game 是游戏真实帧，Display 是实际上屏回调计数；二者不能混作游戏原生帧率。Apple Metal HUD 另由 `--metal-hud` 启用。全屏/HUD 先前已进行真实 AppKit 操作验证。

`assets/AppIcon.svg` is an original project mark, not game artwork. `make mac` renders PNG/ICNS into ignored `work/build/icons/`; the native app loads the generated PNG as its Dock icon. There is no newly packaged installable `.app` release.

## Experimental interpolation / 实验帧生成

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --frame-generation metal --profile
```

MetalFX interpolation is available on the tested M3 Max/macOS environment, so an FSR fallback is unnecessary here. It requires spatial upscaling, direct presentation and a display reporting at least 100 Hz. It is **off by default**. Unsupported menus/movies/passes without validated depth/camera inputs produce no generated frame. Two history frames warm up before presenting an intermediate image.

This prototype snapshots actual 1080p device depth and camera parameters from the captured depth-linearization ABI. GPU image optical flow estimates current-to-previous motion; it does not yet use the game's skeletal motion vectors or separate UI masks. A textured translation fixture achieved 1842/2000 motion samples within two pixels, and the Apple interpolator produced a measured intermediate centroid after warmup. These are synthetic GPU results, **not evidence of correct game interpolation, artifact-free combat, or 120 FPS display pacing**. Disocclusions, transparency, UI and scene cuts need further work; real-game validation remains pending. The correctness-first generated-present path currently waits for copy completion and needs measured pacing optimization.

本机已提供原生 MetalFX 插帧库。实验实现使用实际深度/相机和 GPU 图像光流，不假装已有骨骼运动矢量；默认关闭。光流和 Apple 插帧的合成 GPU 回读测试通过，但游戏内画质、120 Hz 双呈现节拍与切场历史重置尚未验收，不能声称已达游戏 120 FPS。

The referenced [FSR 4 native macOS project](https://github.com/UzenUPoZiTiV4ik/fsr4-native-macos) documents FSR 4.1.1 **upscaling**, not an interchangeable frame-generation implementation. Its existence alone does not establish game frame-generation support.

```sh
make test
.venv/bin/python tests/run_indirect_batch.py  # Includes production D16 array/mip and dormant-stage checks.
.venv/bin/python tests/run_metalfx.py         # Real GPU spatial/motion/interpolation fixtures.
```

All game data, shaders, generated images, measurements and diagnostic logs remain in ignored `work/`. Support legitimate purchases; no NSP or other game content is included.


## iOS native display policy / 手机屏幕策略

See [iOS device notes](IOS.md). The mobile launcher selects original handheld targets/DRS or the exact-build 1568×720 profile from two immutable signed images in one app. The wide profile synchronizes targets, all preinitialized DRS alias limits, primary-camera horizontal FOV and logical HUD size. Existing authored UI compensation remains intact. MetalFX spatial scales the actual source to the native drawable. Mac retains its coherent fixed 1080p→4K policy. The iOS sizing branch has a host GPU regression for 720p→2240×1260 and a drawable resize to 1920×1080, including three-slot output replacement, resource residency and perceptual gray readback. Actual iPhone performance is verified separately.
