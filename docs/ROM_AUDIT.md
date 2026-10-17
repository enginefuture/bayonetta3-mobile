# ROM compatibility audit / ROM 兼容性扫描（2026-10-17）

> 后续修复：此前列出的 457 份小 mip 和 1 份 cube 大小差异已修复，并通过独立 CPU/实际 Metal 4 上传、六面全 mip 和区域写入读回。115 份缺失阶段已进入完整正式缓存 `3dc04cc356e3`。两份 subgroup TES 已保留真实 lane/shuffle 语义并编译，6 份 TES 全部通过实际 Metal 管线创建；当前细分补充库 36 份。Mac 已启动进入战斗，用户反馈正常。下文保留初始扫描证据，不再代表当前待办；剩余旧控制格式、19 份 level 字段、1 份纹理尺寸不一致和未观察 NVN 路径仍需运行证据。

本次只读扫描本机已合并更新的 Bayonetta 3 1.2.0 ExeFS/RomFS，并对照当前 Mac 实现与私有着色器缓存。没有修改 ROM、正式着色器缓存或渲染代码。所有详细资源清单、原始字节、编译产物和诊断数据保留在忽略的 `work/analysis/rom-scan/`，不随源码发布。

## 覆盖范围

- 三个运行模块重新验证 NSO 段哈希；main SHA-256 与固定版本 profile 一致。
- RomFS 共 552 个文件：72 个 PKZ、478 个 WebM、2 个 AVI。
- PKZ 共 12,857,318,528 字节；18,732/18,732 个成员全部展开并检查嵌套目录，解压后 25,828,404,053 字节。发现 136,520 条叶资源记录，扫描错误为 0。记录数包含重复出现的资源，不是唯一资产数。
- 8,024 条着色器资源记录：8,019 条采用已识别控制格式，去重后 6,419 份；另 5 条旧控制格式仍未解释。现有 6,304 份运行采集均能与 ROM 控制段和代码逐字节对应。
- 44,456 条 XT1 纹理记录、22 种格式值、43890 条 2D / 558 条 cube / 8 条 3D。此为静态记录数，不能当作已显示或已正确渲染的数量。
- 478/478 个 WebM 私有转换缓存重新校验通过。两个 720×405、5 秒 MJPEG/AVI 为占位命名资源，未包含在 WebM 预检中，尚未验证实际调用。

## 需要优先处理

| 优先级 | 发现 | 已有证据与边界 | 下一步 |
|---|---|---|---|
| P0 | 两份 TES 的 subgroup 翻译仍失败 | 全盘识别的 5 TCS + 6 TES 已全部出现在采集目录；其中两份 TES 无法经当前 SPIRV-Cross 生成后细分 Metal 函数。当前游戏只验证了一组 VS/TCS/TES，不能保证其他组合 | 保留 subgroup 语义实现 TES 路径，验证真实资源绑定及阶段组合；不能以常量或跳过绘制代替 |
| P1 | 115 份 ROM 着色器未进入正式缓存 | 38 VS、73 PS、4 CS。原始代码已完整校验，115/115 独立 SPIR-V → MSL → Metal 编译通过；实验产物未安装为正式缓存，没有对应场景/资源类型/流水线验收。它们也可能包含备用材质 | 纳入正式离线构建和统一 varying ABI/完整性回执，检查驱动常量、纹理类型及实际组合 |
| P1 | 小 mip 横向 tile 判定遗漏 | 按 block-linear、flags=0 对照当前生产布局计算，44,437 条可解释 level 记录中 459 条总大小与 ROM 声明不等。只在私有实验中补上完整 tile 的宽度条件后，457 条恢复相等；未做像素/GPU回归 | 增加 BC/ASTC、窄长纹理及 mip-tail 的独立参考与 GPU 读回，再修 CPU/GPU/区域写入共同依赖的布局逻辑 |
| P1 | 一份 cube 纹理的面间距不符 | 上述实验剩余一份 cube：当前总大小 2,113,536，资源声明 2,359,296 字节；当前每面 352,256，按 64 KiB 对齐后为 393,216，恰与声明相符。尚未验证实际描述符及像素 | 独立确认 sparse cube layer stride，验证六面和各 mip，不直接改所有 cube 的对齐 |
| P2 | 5 条旧版 shader 控制格式 | 一份头发 VS、字体 VS/PS、两份调试 PS 使用未支持的旧布局（版本字段 1.9）；没有证据表明这些资源已被实际提交 | 确认加载选择规则和 ABI，再决定支持范围；不能只放宽版本检查 |
| P2 | NVN 仍是接口子集 | 当前构建槽表 534 项，308 项注册实现、3 项调试标记、223 项仍是显式失败入口。包括少用查询、advanced blend、subtile/checkpoint 等；这些数字不等于游戏实际缺少 223 个必需功能 | 将 ROM/程序中的函数名与原始调用点和运行计数关联，优先处理真实调用，不给全部入口伪造成功 |
| P2 | 纹理元数据存在未解释情况 | 19 条 level 字段高位非零，已从大小对照排除，未擅自截断成低字节；另有一份 1024² ASTC 的头部尺寸与存储量不符。不能据此认定游戏资源损坏或运行时也采用这些尺寸 | 对照加载器和实际 NVN 描述符，确认 level 字段读取宽度、尺寸覆盖及资源变体 |

### mip 问题的具体证据

某份 512² BC1、10 级 mip、布局 `0304000007000100` 资源声明为 **177,152 字节**，当前算法算得 **209,920 字节**，多出 32,768 字节。问题出在小 mip 只满足高度条件时仍按 16 GOB 列对齐。私有数值实验将横向条件从 `width_blocks >= 64 / bytes_per_block` 改为 `width_blocks >= ((64 / bytes_per_block) << pkg_tile_w)`，整体不一致数从 **459 降至 2**。这说明当前横向布局修复还缺少小 mip 的完整 tile 边界；尺寸吻合仍不证明 texel、mip 偏移和同步全部正确。正式源码保持原状。

两份仍失败的 TES：`17f64cbfcdb0f91f`、`a2d16cf672285e87`；编译器错误为 “Subgroup builtins are not available in this type of function.”。全盘没有发现新的 GS 阶段，现阶段应优先解决实际存在的细分与布局问题。

## 其他验收边界

- 曲面细分仍显式拒绝未验证的 patch/domain、indirect patch draws、deferred tessellation replay 等路径。单独把阶段编译成功不能证明整个绘制组合正确。
- 自动存档、关卡往返、全部音轨和完整流程未验收；静态服务名称不能证明服务调用时序正确。
- 1080p + MetalFX spatial 4K 在此前已观察场景正常；本次没有重启游戏或改变该配置。
- Metal 帧生成仍为实验、默认关闭，缺少完整游戏画面与输入延迟验收。ROM 扫描不能完成这项验收。
- 最新全量 Mac 图形链尚未完成 iOS 构建/签名/安装/真机验证；此前未签名构建不代表真机可玩。

## 可重复扫描

目录级检查（不解压）：

```sh
.venv/bin/python tools/scan_rom.py
```

完整检查需本地构建的隔离 Kraken 解压进程，协议包装源码在 `tools/rom_decoder_worker.cpp`。第三方解压器、其许可证、生成程序及资源只能保存在忽略的 `work/`，不纳入项目运行依赖。示例：

```sh
.venv/bin/python tools/scan_rom.py --deep \
  --decoder-worker "$PWD/work/toolchains/romscan-ooz/decoder-arm-fixed"
```

PKZ/DAT 目录字段与 [Kerilk/bayonetta_tools](https://github.com/Kerilk/bayonetta_tools) 的解析源码交叉核对；XT1 参考 [Noesis 导入器结构](https://github.com/Kerilk/noesis_bayonetta_pc/blob/master/bayonetta_pc/AstralChain.h)。参考解析器不构成游戏兼容性证明。

本次旧版独立扫描解压器曾在四个事件资源上发生栈数组越界；ASan 定位到 6-bit 数组计数与 32 项临时数组不匹配。仅调整私有扫描工具容量后，重新完整扫描 18,732 个成员通过。这是扫描工具问题，不能记为游戏场景崩溃，也没有修改游戏自身的解压器。

主要私有回执：`inventory.json`、`shader-audit.json`、`shaders/uncaptured-build.json`、`texture-layout-audit.json`、`texture-width-experiment.json`、`nvn-source-audit.json`、`exefs-identities.json`。目录和布局检查使用自有合成数据进行边界回归，不包含游戏内容。

## English summary

The local merged 1.2.0 ROM was inspected read-only: all 72 PKZ archives and 18,732 members decoded successfully, yielding 136,520 resource occurrences. The recognized shader corpus has 6,419 unique control/code pairs: 2,045 VS, 4,285 PS, 78 CS, five TCS and six TES. All 6,304 existing captures match original bytes. Another 115 shaders compile offline but are absent from the production cache; five older-format entries remain uninterpreted. Two known subgroup TES still cannot compile for Metal tessellation.

The texture audit covers 44,456 XT1 occurrences. Under the stated block-linear assumption, production size calculations disagree with 459 of 44,437 records with interpretable level fields. A private experiment requiring a complete sparse tile in the horizontal dimension resolves 457 discrepancies numerically. One cube face-stride issue and one header/storage inconsistency remain. Nineteen noncanonical level words require loader inspection. No numerical experiment was installed into the renderer, and size agreement is not pixel or gameplay validation.

All 478 WebM caches pass verification. Two dummy-named MJPEG/AVI resources remain outside that preflight. NVN is a tested subset, not a complete driver. Full-game, frame-generation and iOS-device coverage remain unproven. Detailed resource inventories, original content and generated binaries stay in ignored local storage; the repository distributes source and instructions only, requires users' own lawful dumps, and contains no NSP.
