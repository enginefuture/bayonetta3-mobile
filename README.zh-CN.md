# Bayonetta 3 Mobile

[English](README.md) | 简体中文

面向 Apple silicon macOS 的开源原生兼容层研究项目，用于运行你自己拥有的 Nintendo Switch 版 **Bayonetta 3（猎天使魔女 3）**，现已在 iPhone Air 验证真机运行。基于 [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 与 [blade2-mobile](https://github.com/ha7rock/blade2-mobile) 的方法和代码。

> **支持正版，请购买正版游戏，自行准备自己的游戏文件。**
>
> 本仓库仅提供兼容层源码、构建工具和使用教程。**我们不提供、不托管、不链接、也不接受任何 NSP/XCI/NSZ、密钥、票据、游戏可执行文件、提取资源、原始或翻译后的游戏着色器，以及包含游戏内容的安装包。** 请在允许的范围内，从自己合法拥有的副本准备文件。不要将这些内容上传到 GitHub、Issue、PR、Release 或 Actions 产物。项目不提供游戏下载或游戏文件分享支持。详见[游戏文件政策](docs/GAME_FILES.zh-CN.md)。

这是独立社区项目，并非官方移植，与任天堂、PlatinumGames 或 SEGA 无关联，也未获其背书。游戏名称、商标及内容归相应权利人所有。源码许可证不包含游戏授权。

## 当前状态

以下为 **2026-10-17** 的开发实测，项目仍是研究预览版。

| 项目 | 已实际验证的范围 |
|---|---|
| Apple silicon Mac | 原生启动、标题/菜单、实时战斗及新场景推进；用户确认手柄操作正常 |
| NVN / 图形 | 目标所需的 NVN **55.12**、Metal 渲染及覆盖 2045 个顶点 / 4285 个片元程序的统一接口 |
| 性能 | M3 Max 同一进程开→关→开实测战斗约 **60→18→60 FPS**；后续新场景运行通过 181 组新增配对，无管线致命错误。详见[性能测量](docs/PERFORMANCE.md)，不代表全流程性能 |
| iOS / iPhone | 已在 iPhone Air（A19 Pro、iOS 27.2）运行真实战斗，用户确认声音、真宽屏与 HUD 正常；原 App 内新增启动设置，正常/宽屏、Metal HUD 和 MetalFX 开关均可选择。见 [手机支持说明](docs/IOS.md) |
| 尚待验收 | 完整章节、长期稳定性、音频质量、存档往返、所有图形路径及设备生命周期 |

已知还有材质/发丝/透明效果问题、性能波动和细分覆盖不完整。2045 个顶点库全部通过读取完整插值接口的真实 Metal 管线测试，约 11 分钟跨场景运行正常退出。当前完整缓存包含 6408 个普通阶段及 860 个片元变体；私有细分补充库包含 5 个原始 TCS、全部 6 个 TES 和 25 个候选顶点捕获程序。原先失败的两份 TES 已保留 subgroup 语义实现，6 份 TES 均通过实际 Metal 管线创建；mip/cube 上传及区域写入独立回归通过。这不代表着色器或游戏全流程兼容。实测范围和本地证据路径见 [STATUS.md](docs/STATUS.md)，原始日志与截图不公开分发。

现已接通原始 VS → TCS → Metal 曲面细分器 → TES，越过此前退出点；用户确认在固定 1080p、MetalFX spatial 4K 开启时进入新场景且画面正常。6 组独立 GPU 回归覆盖索引/数组绘制、实例偏移、顶点 divisor、空裁剪和位移深度。更多场景仍需验证，游戏内帧生成为实验功能、默认关闭。见[图形实现与限制](docs/GRAPHICS.md)。

结算画面的紫色色块和烟雾瑕疵已定位为预排布纹理的横向对齐参数被忽略。CPU/GPU 上传、mip 偏移及区域写入现使用统一修正；独立 ASTC 解码和生产 GPU 回归通过，用户确认“紫色块消失，烟雾正常”。其他材质瑕疵仍需分别验证。

## 手机支持

- **已验证设备：iPhone Air，A19 Pro GPU，iOS 27.2。** 开发签名版已运行真实战斗；其他 iPhone 与 iPad 尚未验证，不能据构建目标推断兼容性。
- **同一个 App 内选择：** 每次启动先显示设置页，选择正常 16:9 或扩大左右视野的真宽屏，再独立开关 Metal HUD、MetalFX，点击“开始游戏”。设置会保存；再次打开可修改，无需安装第二个 App。
- **手机专用超分：** 正常模式使用原生掌机画幅；实测宽屏为 1568×720，MetalFX 按手机屏幕尺寸输出，保留纵向视野并适配 HUD，不套用 Mac 固定 4K。iOS 帧生成关闭。
- **构建与限制：** iOS 26+ 是工程最低目标，真机需自行签名及内存相关权限。大量特效时仍会掉帧，尚未完成全章节和长期温控测试。见 [中英双语真机教程与验证范围](docs/IOS.md)。

仓库只发布源码和教程，不提供 NSP、密钥或含游戏内容的 IPA。请支持正版，自行准备自己的游戏文件。

## 实现方式

```mermaid
flowchart LR
    A["你自己的游戏文件：仅本地"] --> B["精确版本检查"]
    B --> C["离线 AArch64 指令改写"]
    B --> D["本地着色器采集与离线翻译"]
    C --> E["原生宿主与 Horizon 服务适配"]
    D --> F["NVN 55.12 转 Metal"]
    E --> G["macOS / 实验性 iOS 外壳"]
    F --> G
```

游戏程序经过离线改写后，以原生 ARM64 代码执行；宿主实现其调用的平台服务，图形层将所需 NVN 操作映射到 Metal。构建阶段使用 Ryujinx 的 MIT 着色器翻译库，**运行宿主不依赖 Ryujinx 模拟器应用**。影片由自己原片生成的本地缓存解码。

当前仅接受配置中的 **Switch 1.2.0**，Program ID 为 `01004a4010fea000`。Build ID 与 SHA-256 不符时停止；默认严格模式遇到未知调用或缺失着色器会明确失败。详见[实现分析](docs/ARCHITECTURE.zh-CN.md)。

## 构建和运行

需要 Apple silicon Mac、macOS 26+、带 Metal 工具链的完整 Xcode、Python、LLVM、.NET 10、SPIRV-Cross、FFmpeg，以及自己的本地游戏文件。开发实测使用 Xcode 27，未验证旧系统/工具链。

```sh
git clone https://github.com/enginefuture/bayonetta3-mobile.git
cd bayonetta3-mobile
make setup
```

继续阅读 **[中文构建教程](docs/BUILD.zh-CN.md)** 或 **[English build tutorial](docs/BUILD.md)**：包括本地准备、改写与验证、从源码构建翻译器、采集/编译/严格运行循环、Metal HUD 及实验性 iOS 构建。干净克隆不含预生成的游戏程序和着色器，完成这些步骤后才能尝试运行。

本地工作区准备并验证完成后：

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud
```

`0` 表示取消诊断时限，关闭窗口或按 Command-Q 退出；加 `--metal-hud-log` 将 HUD 指标写入私有运行日志。

| 键盘 | Switch 输入 |
|---|---|
| WASD | 左摇杆 |
| J / 空格、K、U、I | A、B、X、Y |
| Q / E、Z / C | L / R、ZL / ZR |
| 方向键 | 十字键 |
| Return / Tab | 加号 / 减号 |

## 目录

| 路径 | 用途 |
|---|---|
| `tools/` | 本地准备、模块验证、构建与启动工具 |
| `config/` | 版本指纹及接口名，不含游戏字节 |
| `platform/ios/` | 实验性 UIKit/Metal 外壳及工程配置 |
| `tests/` | 合成改写、ABI 与 GPU 回归测试 |
| `third_party/` | 固定上游版本的源码和许可证 |
| `docs/` | 教程、实现分析、实测状态与上游修改记录 |
| `work/` | **私有且被 Git 忽略**：游戏输入、密钥、存档、生成产物及运行证据 |

## 参与开发

见 [CONTRIBUTING.md](CONTRIBUTING.md)。报告问题时提供系统、硬件、工具版本及脱敏错误摘要，不要附游戏文件或密钥。以下测试不需要游戏文件：

```sh
make test
make test-gpu  # 需要 Apple silicon Mac 和 Metal
```

发布修改前只暂存已审查的源码，再运行 `python3 tools/audit_public.py --all-history`。CI 会重复检查实际 Git 索引和历史，包括强制加入的文件。自动审计不能证明每个字节的来源，提交者仍须人工确认内容。

## 致谢与许可

兼容层源码采用 [MIT](LICENSE)，保留原作者声明。宿主/图形基础来自 blade2-mobile 提交 `c981fcb62fe9962ca81d359f639bd05117bd03b4`，继承 d2r-mobile 的方法与实现。详见[第三方声明](THIRD_PARTY_NOTICES.md)、[上游版本](third_party/UPSTREAM.json)、[修改记录](docs/UPSTREAM_CHANGES.md)和[接口元数据清单](docs/DERIVED.md)。

**仓库不存放任何 NSP，不提供密钥、游戏资源或含游戏内容的下载包。支持正版。**
