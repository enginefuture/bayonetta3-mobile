# 使用自己的游戏文件构建

[English](BUILD.md) · [首页](../README.zh-CN.md)

先阅读[游戏文件政策](GAME_FILES.zh-CN.md)。这是固定 Switch 1.2.0 版本的开发教程，不是游戏下载或一键安装指南。以下命令均在仓库根目录执行，全程不需要上传游戏文件。

## 1. 工具

开发实测环境为 Apple silicon、macOS 26.6.2、Xcode 27.0、.NET SDK 10.0.402。构建最低系统配置为 macOS/iOS 26，旧配置未验证；本流程不支持 Intel Mac 或 iOS 模拟器。

安装完整 Xcode，选中其开发目录，并确保 Metal 编译器组件可用：

```sh
xcodebuild -version
xcrun -sdk macosx metal --version
xcrun -sdk iphoneos metal --version
```

安装 Python 3、LLVM、SPIRV-Cross 和 FFmpeg；Homebrew 用户可以用 `brew install python llvm spirv-cross ffmpeg`。从 [Microsoft](https://dotnet.microsoft.com/download/dotnet/10.0) 安装 **.NET 10 SDK**，仅安装运行时不够。iOS 还需要 XcodeGen（`brew install xcodegen`）。自行准备本地 [NSTool](https://github.com/jakcron/nstool)，开发使用 1.9.2。这些工具与游戏分开，项目不提供游戏或密钥下载。

```sh
make setup
.venv/bin/python tools/setup_shader_tools.py
```

辅助工具从仓库源码构建着色器翻译器，产物全部写入 `work/`。默认选用已有 .NET 10 SDK，也可用 `--dotnet /绝对路径/dotnet` 指定。首次恢复软件依赖可能连接 NuGet，不下载游戏数据。工具会建立本地 SDK 软链接并复制 SPIRV-Cross，供构建包装使用，不获取游戏、密钥或着色器缓存。

## 2. 准备本地输入

替换为**自己**的本体 NSP、1.2.0 更新、密钥和 NSTool 路径；下列占位文件不由本项目提供。

```sh
.venv/bin/python tools/prepare.py \
  --base '/absolute/path/to/your/base.nsp' \
  --update '/absolute/path/to/your/update-1.2.0.nsp' \
  --keys '/absolute/path/to/your/prod.keys' \
  --nstool '/absolute/path/to/nstool'
make analyze
make rewrite
make verify
```

工具检查 PFS0 范围，选取主 Program ID `01004a4010fea000` 而非另一个程序索引，并在 `work/game/` 合并 ExeFS/RomFS；原输入只读。中断后诊断保留在 `work/game.partial/logs`，`--resume` 可复用完整解包成员，不要为重试删除原始输入。

Build ID/哈希不符合 `config/bayonetta3-1.2.0.json` 时，改写立即停止，不要删除校验强行通过。验证需要 LLVM，默认 `/opt/homebrew/opt/llvm/bin`；其他位置运行 `.venv/bin/python tools/verify.py --llvm-bin /path/to/llvm/bin`。启动要求完整验证回执，并再次核对改写产物哈希。

## 3. 准备影片缓存

实测 AVFoundation 路径无法直接解码游戏 VP9/WebM。先由自己的完整影片目录生成 AVC 缓存，包括教学和技能树子目录：

```sh
.venv/bin/python tools/prepare_media.py work/game/RomFS/movie --jobs 2
.venv/bin/python tools/prepare_media.py work/game/RomFS/movie --check
```

缓存及清单位于 `work/media/`。工具检查帧数、尺寸、时间和支持的范围元数据后，才原子发布缓存及包含原片/输出校验和的回执；重试复用有效缓存。AVC 为有损转换，画面/音频质量仍须检查。启动默认核对全部原片和缓存哈希，避免到后续章节才因未准备影片而退出。`--skip-media-preflight` 仅为显式诊断例外，不能让缺失缓存的场景正常播放。也可传入单个原片路径定点修复。不会下载或上传游戏数据。

## 4. 从自己的文件建立着色器库

仓库不分发游戏着色器库或采集表。先构建宿主，再用**诊断采集模式**观察自己的游戏着色器：

```sh
make mac
.venv/bin/python tools/run_mac.py --seconds 120 --capture-shaders
```

J/空格确认标题和菜单。采集模式遇到缺库会省略绘制，画面可能不完整或黑屏，**不能作为可玩验收**。代码、纹理事实和阶段配对只记录到私有 `work/`。120 秒诊断看门狗可能以 142 退出，这代表达到时限，不是兼容性通过。

关闭宿主后冻结采集输入并编译：

```sh
.venv/bin/python tools/build_shaders.py --jobs 8
make mac
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud
```

编译流程打包采集、冻结阶段配对、记录工具指纹，翻译受支持阶段、生成 Metal 库并更新链头文件。必须重编宿主，使其核对同一链版本。实际渲染验收不要带 `--capture-shaders`。

进入新场景可能遇到缺库或新顶点/片元接口。按“采集 → 关宿主 → 编译 → 重编宿主 → 严格运行”迭代。事实和配对取决于实际走到的路径，开场也可能需要多轮，后续章节未验证。存在 `work/shaders/used.txt` 后可用 `--used-only` 只编译已观察的提交键。未支持的细分阶段会单独报告，不能靠忽略构建错误解决。

## 5. HUD、操作与诊断

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud-log
```

该命令只为子进程开启 Apple Metal HUD 及控制台统计。`--seconds 0` 保持窗口，关闭窗口或 Command-Q 退出；未指定时默认是 30 秒诊断。日志位于 `work/run/log/`，存档位于 `work/run/save/`，不使用模拟器存档；按键见首页。

针对具体问题使用 `--trace-fs` 或 `--trace-nvn`。日志保持私有，仅分享脱敏错误摘要。采集画面和进程存活时长不代表可玩；开场 HUD 指标也不能代表战斗或全流程性能。

战斗和章节切换诊断：

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud --profile
.venv/bin/python tools/analyze_run.py work/run/log/native-YOUR-RUN.log
```

每次启动生成原始 `.log`、影片 `.preflight.json`、含宿主/着色器身份与选项的 `.session.json`、`.events.jsonl` 和退出 `.summary.json`。即使原生宿主中止，父进程仍记录退出原因，区分缺影片、着色器/管线失败、原生崩溃和诊断超时；这些摘要不表示可玩验收通过。`--profile` 增加逐帧 `.frames.tsv`、长帧诊断及深度复制次数/传输量。逐帧表默认上限 32 MiB（`--profile-log-mib 1..256`），达到上限明确记录，普通统计窗口继续。分析器输出私有 `.analysis.json`；被截断的前段采样不能当作整次性能数据。

可另开 `--gpu-profile --gpu-profile-every 60`，将抽样 Metal 4 渲染/计算/复制 encoder 时间戳写入 `.passes.tsv`（上限 32 MiB）。精确探针可能拆分 encoder 并改变性能，须与 FPS 对比运行分开。不同 encoder 时间跨度可能重叠，不能相加。`-1` 表示没有可用时间戳（包括空通道/仅清屏的渲染通道），不代表 GPU 成本为零。所有日志和采集数据都保留在忽略的 `work/`。

Metal 4 路径会在已证明只读的命令段内批量准备 GPU 间接绘制参数；计数仍由 GPU 读取，保留绘制、画质与游戏逻辑。复制、上传、计算、清除、事件、查询、附件改变、未知反射及可能覆盖输入的写入都会截断批次。`--indirect-batch 0` 选择原准备路径作为对照。进程内诊断 A/B 可加 `--indirect-batch-control work/run/batch-policy.txt`，向这个本地文件写入 `0` 或 `1`；每 60 帧轮询，切换日志包含实际帧号。保持视角/场景及 HUD/探针设置一致，丢弃切换窗口，对照 `@frame_ms`、`@gpu_ms`、`@passes` 和 `@indirect_batch_*`，不要把精确探针运行与正常 FPS 运行混比。

## 6. 实验性 iOS 构建

先完成 Mac 采集/严格运行循环，再编译已观察路径的 iPhoneOS 着色器和未签名 App：

```sh
.venv/bin/python tools/build_ios_shaders.py --jobs 8
.venv/bin/python tools/build_ios.py --bundle-id org.example.bayonetta3mobile
```

生成 `platform/ios/Bayonetta3IOS.xcodeproj`，本地 App 位于 `work/ios/`。**未签名 App 不能安装。** 源码构建不证明真机兼容；本项目尚未验证签名安装及设备运行。

配置自己的 Xcode 账号、开发团队、唯一 Bundle ID 和适当权限后，可以尝试本地签名：

```sh
.venv/bin/python tools/build_ios.py --sign --team-id YOUR_TEAM_ID \
  --bundle-id YOUR_UNIQUE_BUNDLE_ID
```

描述文件错误见 `work/build-ios.log`。当前外壳请求较高内存上限和扩展虚拟地址权限，账号权限及真机内存限制仍须验证。此命令只签名构建，不执行安装。**不要公开生成的 App/IPA，其中内嵌游戏程序和着色器。**

后续设备实验中，外壳要求容器 `Library/Application Support/romfs` 存放完整自有 RomFS，`Documents/media` 存放影片缓存。`core_000.pkz` 是资源标记，只复制该文件不够；日志在 `Documents/boot.txt`。容器传输、签名和设备行为仍是待验证的开发工作，不是已经支持的用户安装流程。

## 7. 纯源码测试与发布

```sh
make test
make test-gpu
python3 tools/audit_public.py --all-history
```

前两项使用合成输入，不需要游戏文件。审计检查暂存/索引，`--all-history` 还检查可达历史中的对象。不要强制加入 `work/`、密钥、采集、安装包或游戏内容，详见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

着色器构建现在先解码**全部已采集片元输入**（即使使用 `--used-only`），再为顶点程序导出完整兼容的插值接口；不再要求先遇到每一种阶段配对。构建核对实际生成的图形接口并写入私有 `_interfaces.json` 完整性回执，普通 Mac 启动检查回执及对应库；预检失败时重新构建着色器和宿主。尚未采集的程序、未支持的细分阶段仍是独立限制。回执和游戏派生库均保留在忽略的 `work/`。
