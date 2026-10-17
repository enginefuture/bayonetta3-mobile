# 实测状态（2026-10-17）

目标为本机 Bayonetta 3 1.2.0、Program ID `01004a4010fea000`。优先完成 Mac 实际运行，再推进 iOS 真机。**Mac 实时战斗及新场景切换已实测，优化开关对照约 18 → 60 FPS，用户确认画面和帧率正常；完整关卡稳定性及 iOS 真机尚未验收。**

| 阶段 | 证据与结果 |
|---|---|
| 自有资源 | 只读使用本机本体/更新 NSP、已有 keyset，更新合并成功 |
| 模块固定 | main/subsdk0/sdk 的 Build ID、SHA-256 固定于 config |
| 离线改写 | 三模块独立结构/等价/变异检查通过；没有游戏逻辑剪口 |
| macOS 构建 | Apple silicon 原生宿主增量构建通过 |
| SDK / NVN | SDK 初始化、文件读取、CoreAudio 创建、NVN 55.12 初始化已执行 |
| 实际画面 | 严格着色器模式下已渲染标题、主菜单、难度及模式说明页 |
| 输入 | 原生 NSEvent → 宿主 Npad → 游戏，已观察标题进入主菜单及后续页面 |
| 实时 3D 场景 | 严格模式已显示实时人物/敌人/特效，用户确认战斗可操作及优化后约 60 FPS；完整关卡待验收 |
| iOS | 此前 iPhoneOS 未签名构建通过，507 基础着色器 + 95 变体已打包；最新 Mac 统一链尚未重新验证 iOS 构建，签名因 No Accounts / 缺描述文件失败，未安装/未真机运行 |

## 当前 Mac 状态：性能与统一接口跨场景复测通过

后续严格运行 `work/run/log/native-20261017-122101-73785.log` 的帧 6000–9000 持续约 60 FPS，用户确认帧数稳定，但再次进入新场景时因另一组 VS `51c594affde74cc9_b` / FS `a593c39e7f07769d_b` 缺少 `locn4` 原生中止（-6）。这说明只更新“已观察配对”不足以覆盖新场景。

现改为离线解码全部 4212 个已采集片元程序，合并实际输入需求（位置 0–13，共 56 个分量），让全部 2007 个顶点程序在原始指令执行前沿用翻译器既有输出初始化路径导出统一接口；原始写入仍覆盖对应分量。与首次遇到的组合无关，不在运行时补改 MSL、不跳过绘制。完整接口进入 CAS 指纹，实际工具锁和宿主链更新为 `220ab21bd6d9`。新增所有实际图形接口静态覆盖与哈希回执检查；普通 Mac 启动会拒绝旧链、缺失、变更或额外未校验图形库。其他目标保持原有配对逻辑。

本次旧链实际 Metal 测试重现 `locn4` 拒绝，统一接口新库已通过这组真实管线创建。6293 个支持阶段全部重编通过；全部 2007 个真实顶点库与读取完整 14 个位置的测试片元均通过实际 Metal 管线创建（含点图元所需拓扑与整型顶点输入配置），不是只测失败的一组。静态检查覆盖 2007 个顶点 / 4212 个基础片元 / 830 个片元变体，共核对 19489 份库、MSL、反射及构建回执哈希。普通回归 29 项 Python 与 C 全部通过，Mac 宿主构建成功。私有日志为 `work/{build-translator-varying-abi,build-shaders-varying-abi,build-mac-varying-abi,test-shader-corpus,test-varying-abi-final,locn4-old-pair-test,locn4-new-pair-test}.log`，私有静态回执为当前链的 `_interfaces.json`。

统一版已实际启动：`work/run/log/native-20261017-123809-43769.log`，478 份影片及全部图形接口预检通过，Metal HUD / 间接绘制批量准备开启，精确 GPU 探针关闭；帧 2700 / 3000 的窗口中位帧时间均为 16.65 ms、GPU 9.01 / 8.64 ms，已观察实时人物、敌人和特效截图（`work/run/varying-abi-2400.png`）；原性能收益仍在。用户随后确认“已经进入新场景了，这次没跳出，帧数也正常”。完整运行持续 696.86 秒、最后汇总帧 41400，最终退出码 0 / normal_exit，无 FATAL 或 Metal 管线拒绝。运行期记录了冻结图以外的 181 组新增 VS/FS 配对；将其与旧链 `c18263f751f5` 的实际接口比较，其中 7 组存在缺失/不匹配插值，而统一版没有因此中止。这是统一方案覆盖未预先观察组合的实际证据。最近五个 300 帧窗口的帧时间中位数 16.65–16.69 ms、GPU 3.54–5.61 ms。个别首建管线尖峰及上屏异常仍有记录，不能据此宣称全程零卡顿。私有确认摘要为 `work/run/varying-abi-scene-validation.json`。此方案覆盖已采集库中的未遇见配对；未采集的着色器、未支持的细分阶段以及其他服务/资源错误仍须分别处理，不能保证任何场景都不会退出。

The previous per-pair rebuild reached stable combat but another scene exposed a different missing varying. The new offline path decodes all 4212 captured fragment inputs and gives every vertex shader a compatible interface through the translator's existing initialization semantics, preserving original stores. Coverage and integrity are checked before normal Mac launch. All 6293 supported stages compile, all 2007 real vertex libraries pass Metal pipeline creation against a fragment consuming the complete interface, and the 830 fragment variants are included in coverage/integrity checks. The user confirmed the new scene and normal frame rate. The 696.86-second native run exited normally with no fatal pipeline errors and encountered 181 new stage pairs; seven have incompatible interfaces in the previous cache. Recent frame-window medians were 16.65–16.69 ms. This verifies the observed transition and corpus-wide fix, not every chapter or hitch-free presentation. This does not claim universal crash freedom.

### 已验证的性能对照

2026-10-17，同一 Mac 进程、Metal HUD 始终开启、精确逐 encoder 探针关闭，运行中切换间接绘制批量准备。关闭实际发生在帧 4560，恢复开启在帧 5400。排除切换段后：

| 指标（窗口中位数） | 开启前段 | 关闭 | 再次开启 |
|---|---:|---:|---:|
| 帧时间 / 对应 FPS | 16.66 ms / 60.04 | 55.76 ms / 17.93 | 16.66 ms / 60.03 |
| GPU 命令执行时间 | 8.40 ms | 44.91 ms | 8.84 ms |
| NVN 提交时间 | 3.84 ms | 9.59 ms | 3.97 ms |
| 渲染通道 / 帧 | 87 | 646 | 84 |
| 绘制调用 / 帧 | 1593 | 1630 | 1702 |
| GPU 批量准备组 / 帧 | 3 | 0 | 3 |
| 批量处理请求 / 帧 | 536 | 0 | 583 |

用户确认约 60 FPS、人物/敌人/特效画面正常，并确认反向关闭时明显下降。窗口分别为帧 [3300,4200)、[4620,5280)、[5520,6480)；场景继续变化，绘制数相近但并非完全固定负载，不能据此宣称全游戏稳定 60 FPS。机制与复测方式见 [性能优化说明 / Performance](PERFORMANCE.md)。私有证据为 `work/run/log/native-20261017-120804-40430.{log,frames.tsv,session.json,summary.json}` 和 `work/run/indirect-batch-ab-validation.json`。

该次运行随后在新场景原生中止（returncode -6），明确错误是 Metal 管线接口拒绝：VS `89195c3f3bba0bf1_b` / FS `c6fbe54901a89c6b_b` 的片元输入 `user(locn3)` 没有对应顶点输出。运行时记录的真实阶段配对已加入冻结图；据此重新翻译 VS 并生成新链 `c18263f751f5`（旧链 `a628a7bb5ed1`），6293 个支持阶段全部成功，11 个细分阶段仍不支持，Mac 宿主重新构建成功。使用这组真实离线库的独立 Metal 测试：旧链重现拒绝，新链实际管线创建通过。没有用常量补空插值、跳过绘制或关闭严格检查。新链已实际启动（`work/run/log/native-20261017-122101-73785.log`），478 份影片预检通过，已重新进入战斗；帧 6000 / 6300 的 300 帧窗口中位帧时间 16.65 / 16.67 ms、GPU 7.57 / 8.67 ms，批量准备持续生效。该次后续仍在另一组新配对（`locn4`）退出，现已改用上文统一接口方案。私有日志为 `work/{build-shaders-newscene-locn3,build-mac-locn3,locn3-old-pair-test,locn3-new-pair-test}.log`。

In-process ON → OFF → ON testing measured approximately 60 → 18 → 60 FPS with the HUD enabled throughout. The user confirmed normal combat rendering. The later scene exit was a specific vertex/fragment interface mismatch; rebuilding from the observed pair graph fixes actual Metal pipeline creation for that pair. The later corpus-wide native retest above passed user-confirmed scene progression. Neither full-chapter stability nor iOS device gameplay is claimed.

## 已解决的第一章退出与历史性能基线

章节切换存在两个独立退出原因，已分别处理。`native-20261017-110348.log` 在请求 ev0021 时缺少准备缓存而中止；现已递归准备并核对全部 478 份影片，启动默认核对原片/输出哈希与成功回执。`native-20261017-112614-70034.log` 已实际打开 ev0020/ev0021，但在影片收尾后 SIGSEGV，SDK PC `+0x36e3e0`，x0=0。本机确切模块导出定位为 `nn::oe::MuteRecording`，原 SDK 访问没有初始化的系统录像服务对象。已补齐宿主录像静音/恢复策略适配，保留游戏声音及原始游戏逻辑。

严格运行 `work/run/log/native-20261017-113649-82066.log` 已记录 ev0020/ev0021、`[recording-policy] muted=1 recorder=unavailable playback=unchanged`，随后持续提交实时战斗帧；用户确认可进入战斗。存档备份在 `work/backups/save-before-chapter-fix-20261017/`。

批量准备修复前，该战斗场景约 17–20 FPS，GPU 窗口约 40–49 ms，提交约 8–9 ms，每帧约 590 个渲染通道。CPU sample 的游戏线程 3011/3733 样本在 QueueWaitSync→mtl_wait；逐次间接参数准备造成大量通道切换，是后续优化的重点。附件 load/store 字节是描述符范围估算，不能当作硬件 DRAM 流量；逐 encoder 计时用于归因，未用于上述 FPS 对照。历史日志留作诊断，不代表当前优化效果未验证。

## 当前真机阻塞

此前 iOS 未签名构建已通过（`work/build-ios-unsigned-final.log`），实际 Mach-O 平台 IOS、最低 26.0，包含当时冻结链的 602 个 iphoneos 库；最新 Mac 统一链未重编/真机验证。签名重试返回 `No Accounts` 和 `No profiles for com.tabshi.bayonetta3mobile`（`work/build-ios-sign-final.log`）；本机有证书，但 Xcode 未配置可生成该 App 描述文件的账号。需在 Xcode → Settings → Accounts 登录有开发团队权限的账号后继续签名安装。未尝试将未签名包安装到设备。产物清单为 `work/ios-build-validation.json`。

## 公开源码构建检查（2026-10-17）

最新待发布 Git 索引已再次导出到独立的纯源码目录（`work/publish/source-snapshot/`），未复制任何游戏资源。当前 Mac 宿主及 vendored .NET 翻译器均从此导出源码构建成功；本机 `make test`（29 项 Python 与 C）及全部六组 `make test-gpu` 回归通过，包括精确 GPU 探针与生产间接批量路径。源码索引及所有可达历史扫描 985 个 blob / 11.41 MiB 通过；只推送源码与教程。私有构建/测试日志在 `work/publish/`。以下为此前首次公开检查的历史记录。

已从 Git 索引单独导出待发布源码，不复制游戏文件、改写映像、着色器或影片缓存。该独立目录的 Mac 宿主从源码编译通过，.NET 10 翻译器从 vendored 源码 publish 成功，18 项 Python 回归及 C 回归通过；Metal alpha 32 项、已有深度 24 像素、间接参数 8 组、无附件片元 3 组通过。本地日志为 `work/public-mac-build.log`、`work/public-translator-build.log` 和 `work/public-regressions.log`，均不公开。此检查证明公开源码可构建及合成测试通过，不等于从零完成游戏采集、全流程运行或 iOS 真机验收。新增中英文教程和暂存/历史对象审计；所有游戏内容仍保持私有。

## 最近严格运行证据

2026-10-17 的实体手柄测试日志 `work/run/log/native-20261017-110348.log` 与同名 `.hid.jsonl` 仅留本地；开启 HUD 和真实 Npad 返回收样，未启用自动输入。GameController 在初次枚举 0 个后通过连接通知识别 `DUALSHOCK 4 Wireless Controller`（DualShock 4），说明不能仅凭启动瞬间的枚举数判定未连接。游戏实际返回已观察双摇杆、○/×/△/□、R1/R2、Options 和十字下；用户随后确认手柄操作正常。默认位置映射为 ○→A、×→B、△→X、□→Y。收样达到 1024 条后明确截断，未收齐的键不能判为失败；断连重连、所有按键、触摸板/震动并未逐项验收。私有摘要为 `work/run/controller-validation-20261017-110348.json`。

同次运行用户报告战斗/大量特效持续掉帧。Apple M3 Max 上，帧 16500/16800/17100 的 300 帧窗口中位帧时间分别 42.63/45.18/48.16 ms，提交+出图 15.19/12.88/11.51 ms，GPU 25.97/29.61/34.94 ms；帧 17400–18300 持续约 20–23 FPS。GPU 栏是命令缓冲执行时长累计，不是硬件利用率或逐通道独占耗时。战斗采样 `work/run/combat-scene-sample-20261017.txt` 中，游戏主线程 1834/3515 个采样落在 QueueWaitSync→mtl_wait，提交线程也有明显纹理事实记录的 NSString 格式化热点（`texfacts_note`，普通严格运行仍由启动器启用）。支持“渲染执行与兼容层提交开销共同限制吞吐”的判断；尚未定位最重的具体 GPU 通道，不能直接断定某个着色器或硬件算力不足。

另有首次管线/库创建尖峰：帧 9749 为 621.5 ms（同帧创建累计 621.6 ms），帧 12382 为 419.6 ms（创建累计 407.7 ms）。着色器离线编译不等于管线组合提前创建；启动器当前 `DM_PSO_MANIFEST=off`。一些约 350–470 ms 长帧没有对应管线/上传尖峰，原因仍待查，不能全部归于编译。重特效长帧中的纹理上传多为 0–0.2 ms，当前证据不支持将其列为持续掉帧主因。后续应先量化/消除诊断热路径开销，采集战斗逐通道 GPU 计时，再检查深度快照/重复通道读写等保守适配成本，并验证预热/缓存对首次卡顿的改善。性能窗口摘要为 `work/run/combat-performance-windows-20261017.json`；本轮只分析，未修改运行中渲染行为。

2026-10-17 10:31 的 Mac 交互运行已开启 Metal HUD 与其日志，未设置 watchdog、着色器采集或深度探针；日志为 `work/run/log/native-20261017-103105.log`。原生输入脚本在前 24 秒进入 Continue 并跳过初始影片，此后交给用户操作。Apple `metal-HUD:` 统计持续输出；开场采样的 300 帧窗口（3300–4200）帧时间 p50 为 16.63–17.12 ms，GPU p50 为 11.09–11.65 ms，约为 60 FPS。HUD 也记录了部分 25 ms 帧间隔及一次约 8050 ms 的长间隔，原因未定位，不能据此宣布稳定 60 FPS。10:32:20 后进程退出码 0；没有持续运行到全流程验收。启动器新增 `--metal-hud` / `--metal-hud-log` 和 `--seconds 0` 便于复测。

`work/run/log/native-20261017-053745.log` 没有设置采集或深度探针。`work/run/noattachment-1800.png`、`noattachment-2400.png` 分别显示开场环境/巨兽和贝优妮塔人物。GPU 小缓冲回读从全零恢复到非零曝光增益（例如 0.0358968），最终合成已包含实际 3D 人物与场景；这不是替换视频或演示场景。已检查原片 ev0005 的独立参考帧，内容也与这些实时绘制画面不同。

此前 `native-20261017-053106.log` 的 GPU 回读记录 48 批间接绘制，其中 24 批有非零参数；HDR 目标 ser34 已有模型，ser277 仍黑。根因为上游缺少无附件片元通道：曝光计算被跳过，曝光缓冲一直为零。此前只显示背景和少量特效的截图不能作为可玩证据。

最近完成的严格复测为 `work/run/log/native-20261017-061315.log`（275 秒时限，分离左右长按与动作键，密集采样战斗段）。已修复后台管线预测的状态污染：原先阶段绑定在独立静态数组中，预测结束恢复 S 却未恢复绑定；state_op 也会改 R 中的裁剪框。现在阶段绑定随 S 保存/恢复，目标的预测还原 R。`061010.log` 的恢复测试随后暴露组合表线性扫描瓶颈，sample 记录提交线程 663/719 个样本在该查找处；已主动结束该诊断运行，退出 0 也不是游戏流程通过。现改用规范化完整身份键的哈希表，新增键填充/代际/索引隔离检查。本轮 `061315.log` 满 275 秒，定时截图 `controlled-201/205/213/217.png` 与 Npad 收据显示右移、反向左移和转向；`225..241` 的定时帧显示后续动作姿态反馈。基础操作已观察，命中/伤害、完整战斗和关卡仍未验收。证据索引为 `work/run/control-evidence.json`。

`native-20261017-054957.log` 曾在旧状态实现下运行满 420 秒，`strict-extended-7200.png` 显示实时人物/场景，`strict-extended-12600.png` 显示后续实时敌人场景。后续原片帧不作 3D 证据。518 条 Npad 收据完整记录左右满量程及动作键。这只能证明该次路径持续执行，不能证明状态隔离或完整可玩。

随后 `native-20261017-055702.log` / `060610.log` 分别在约 110 / 135 秒因 VS/FS 接口拒绝而中止；前者 b081cabf9dd7ec7f / 3cb146d2bf480fe6 缺 locn2，后者 ee51b41c9103870a / 4b4df547f1232c70 缺多个插值。后续源码追踪发现上述前瞻绑定污染，因此不能把这些组合都认定为游戏实际要求。独立 Metal PSO 测试重现了旧接口拒绝；配对重译后前一组通过，只证明接口可以创建。

另已修复构建可复现性：规范化图形配对快照纳入翻译链哈希，避免新增接口仍共用旧链号。链 `88457687d11e` 全量支持阶段 6293/6293 编译通过（11 个 TCS/TES 仍不支持）。此前严格缺库日志 `053917` / `054207` 和采集日志 `054023` / `054404` 留作诊断历史；采集画面不能作验收。

上述限时日志中的退出 142 来自显式诊断时限（最近一次为 275 秒；此前有 420 秒运行），不是自然退出成功。材质/发丝等细节仍需检查；音频质量、命中/伤害及完整存档往返未验收，不能据此宣布 Mac 全流程可玩。iOS 已完成 Mac 实测路径的 iphoneos 着色器和未签名构建；设备连接/开发模式/本机签名身份已只读确认，仍无本项目签名安装或设备运行证据。

## 本轮修复与已知限制

- 原 NVN 53.311 版本阻塞已被接口子集适配取代。目标报告 55.12，保留游戏检查，其他目标版本不变；这不是完整 NVN 55 驱动。
- SDK 实际纹理对象/视图为 128/16 字节，旧 192/40 字节结构越界。已修复内部尺寸与 SDK 视图位域，并用 canary 验证。
- GPU code 混合版本 1.12/14/15/16，控制段分别为 0x838/848/850/880。哈希、快照和打包按实际长度。
- 修复 ProgramSetShaders 控制段/代码的生命周期；新增 deferred 绑定在提交时冻结数组、GPU buffer clear、GPU 间接绘制、alpha-test、深度 clamp、纹理 swizzle 和区域写入等。详细语义/拒绝路径见 NVN55.md。
- 新 SDK 的 AudioOut 重载、缓冲事件、设备增益、触屏快照、pushed user、保存目录查询均接入宿主语义；离线 PREPO 返回不可用。CoreAudio 已创建，实际声音尚未验收。
- 捕获旧文件 `4b9d39d6e030c3e6.code` 曾为 0 字节，导致误判计算着色器及翻译失败。已原子发布采集、检查配对长度并重捕获为 1792 字节图形代码；打包前严格校验，拒绝截断输入。
- 已捕获约 6300 份着色器。11 个细分阶段（TCS/TES）明确标识为暂不支持，不能把支持阶段编译成功描述成全量支持。实际数量与清单以 `work/shpack/capture_report.json` 为准。
- 不支持不同字节布局的纹理视图、非 COPY logic op、非 1.0 线宽、启用有损 color reduction；调用会明确失败。复杂纹理别名、完整驱动常量和所有阶段仍需实际关卡验证。

## 改写与回归

| 模块 | 结构站点 / 窗口 | 等价站点 | 随机试验 | 分歧 | 变异检出 |
|---|---:|---:|---:|---:|---:|
| main | 12,111 / 26 | 12,111 | 37,546 | 0 | 100/100 |
| subsdk0 | 10,541 / 0 | 10,541 | 32,204 | 0 | 100/100 |
| sdk | 14,083 / 6 | 13,965（另 118 个宿主门做结构核对） | 42,720 | 0 | 100/100 |

`make test`：29 项 Python 回归及实际 C 服务 canary、deferred 时序/分块、NVN55 对象和视图字节布局、纹理区域/其他 mip 保留测试通过。`make test-gpu`：八种 alpha 比较含边界/NaN 的 32 项 Metal 回读通过。另有 24 像素存储深度/副作用、8 组 GPU 间接计数准备及 3 组无附件片元写入回读通过。这些不能证明完整游戏流程；Unicorn 等价试验会替换双方独占指令，也不能证明并发/独占监视器语义。

下一验收优先扩大 Mac 跨场景覆盖及完整关卡稳定性，再推进音频、存档读写与 iOS 签名安装、地址空间、内存、GPU、输入和生命周期。所有游戏文件、密钥、日志、截屏、采集与生成产物留在被忽略的 `work/`。
