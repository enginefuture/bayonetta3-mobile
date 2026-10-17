# Mac 性能优化 / Mac performance optimization

2026-10-17，Apple M3 Max，第一章实时战斗。同一进程开启 → 关闭 → 恢复开启间接绘制批量准备，Metal HUD 始终开启，精确 GPU 探针关闭。用户确认优化后约 60 FPS、画面正常，反向关闭后帧率下降。

| 窗口中位数 / Window median | 开启 / ON | 关闭 / OFF | 再开启 / ON again |
|---|---:|---:|---:|
| 帧时间 / Frame time | 16.66 ms | 55.76 ms | 16.66 ms |
| 1000 / median frame ms | 60.04 FPS | 17.93 FPS | 60.03 FPS |
| GPU command execution | 8.40 ms | 44.91 ms | 8.84 ms |
| NVN submission | 3.84 ms | 9.59 ms | 3.97 ms |
| Render passes / frame | 87 | 646 | 84 |
| Draw calls / frame | 1593 | 1630 | 1702 |

窗口为帧 [3300,4200)、[4620,5280)、[5520,6480)，实际切换发生在 4560 / 5400。战斗继续变化，负载并非逐帧完全相同；结果证明该场景收益可逆，不代表所有关卡稳定 60 FPS。

These windows show a reversible improvement in real combat, with user-confirmed normal rendering. The scene continued evolving; this is not a perfectly fixed workload or a full-game 60 FPS guarantee. FPS above is derived from median frame time.

## 优化手段

原兼容层对每个 `MultiDrawIndirectCount` 单独关闭渲染通道、运行 GPU 参数准备、再开启通道。战斗中每帧数百次操作，反复产生 encoder、同步和附件加载/存储成本。

现在提前扫描同一提交内的安全命令段，把间接参数准备合为少数 GPU 批次，随后按原顺序绘制。计数仍由 GPU 读取、截断并屏蔽未使用项，不做 CPU 计数回读；保留原始绘制调用及图像内容。满足依赖条件时继续使用当前渲染通道，减少重复加载/写回。

边界判断包括固定附件、执行中的图形阶段只读证明、输入与附件底层分配不重叠。计算阶段可同时绑定，但图形绘制不执行它，因此不能误用其写标志阻止批量化。反射识别真实 `samp_tex` 与宿主只读常量 `support`；未知或可写用途仍拒绝。扫描不修改实际运行状态；遇上传、复制、计算派发、清除、事件、查询、未知命令等即截断。活跃描述符命名空间、阶段覆盖和附件别名也会触发必要边界，保留原有同步及深度快照。

辅助优化把纹理事实去重改成完整数值键，减少逐绘制 NSString 分配。它改善 CPU 热路径，但上述大幅收益主要由间接参数准备及安全通道续用的开关对照确认。没有降低分辨率、删特效、跳绘制或全面开启其他 TBDR 优化。

## How it works

The original adapter ended and restarted a render pass for each indirect-count preparation dispatch. Hundreds of such boundaries per frame amplified encoder creation, synchronization and attachment load/store costs.

The new path scans a safe segment of the same submission and prepares indirect arguments in a few GPU batches. Counts remain GPU-resident, original draws execute in order, and eligible draws continue in the current render pass. Batching requires unchanged attachments, read-only executing graphics stages and no input/attachment allocation overlap. A separately bound compute stage is not executed by a graphics draw and is excluded from that proof.

Uploads, copies, dispatches, clears, events, queries, unknown operations and unsafe reflection stop the scan. Descriptor namespaces, stage overrides and allocation aliases are checked before continuing a pass. Existing required synchronization and depth snapshots remain. Numeric fact keys also remove repeated Objective-C string allocation from the observation path. Resolution, effects and draw content are preserved.

## 本地复测 / Local reproduction

先按构建教程使用自己合法持有并自行导出的文件准备环境。本仓库不提供 NSP、密钥、存档或游戏派生着色器缓存。

Prepare your own lawfully obtained and personally dumped files using the build guide. No NSP, keys, saves or game-derived shader caches are distributed.

```sh
printf '1\n' > work/run/indirect-batch-control.txt
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud --profile \
  --indirect-batch 1 \
  --indirect-batch-control work/run/indirect-batch-control.txt
```

进入同一场景后，在另一终端向控制文件写 `0` 关闭，写 `1` 恢复；日志记录实际生效帧。保留 HUD 状态，排除切换窗口并比较帧时间、GPU 时间、提交时间及通道数。精确 `--gpu-profile` 探针会影响性能，单独用于归因。附件流量字段是描述符范围估算，不能当作硬件 DRAM 计数。

Write `0` or `1` to the control file from another terminal to switch within the running process. Keep the HUD configuration fixed and exclude transition frames. Use precise GPU probes in a separate attribution run; attachment byte estimates are not hardware bandwidth measurements.

生产路径合成 GPU 回归覆盖动态 GPU 计数、混合参数格式、别名/写用途拒绝，以及 8 个通道合成 1 个后与独立预期一致的 64 像素回读。测试和实战开关对照分别提供语义与性能证据；新场景稳定性按 [STATUS](STATUS.md) 单独跟踪。

Production-path synthetic GPU tests cover dynamic GPU counts, mixed argument formats, alias/write rejection and pixel equality against an independent expected result when eight passes become one. Scene-transition stability is tracked separately in [STATUS](STATUS.md).

## 跨场景复测 / Scene-transition retest

统一接口版运行 696.86 秒，用户确认进入新场景、帧率正常；无管线致命错误，最终正常退出。实际经过冻结图以外的 181 组新增配对，其中 7 组在旧库中缺少对应插值。最近窗口中位帧时间 16.65–16.69 ms。首次管线创建和上屏尖峰仍有记录；不是所有关卡零卡顿的保证。

The unified-interface build ran for 696.86 seconds and passed user-confirmed new-scene progression. It encountered 181 new stage pairs, including seven incompatible with the prior cache, without fatal pipeline errors, then exited normally. Recent median frame times were 16.65–16.69 ms. Pipeline-creation and presentation hitches remain; full-game stability is unverified.
