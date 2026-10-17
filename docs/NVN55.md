# NVN 55.12 适配记录

这是针对固定 Bayonetta 3 1.2.0 模块的接口子集，不是完整 NVN 55 驱动。未知调用仍中止。主程序的版本检查保持原样；目标构建报告 55.12，其他目标保持原版本。

## 本机 SDK 证据

用已校验的 SDK NSO 建立只读逻辑映像，并解析动态重定位后的函数表。532 个函数名按排序索引对应实现，原始分析留在忽略目录 `work/analysis/`。

- Deferred 绑定：SDK 将 stage、first、count 和 CPU 数组指针写入命令记录，录制时不读取数组。宿主在 QueueSubmitCommands 展开调用/跳转并冻结数组，随后所有 Metal 前瞻和回放共用同一份记录。支持 UBO、SSBO、纹理、图像和分离采样器。限制无效范围、不可读指针、递归深度和输出尺寸。
- ProgramGetSubtileSize：SDK 读取 program 内保存的调度值；宿主保存自己的值，零表示不覆盖 Metal 的自动调度。OverrideSubtileSize 和 ZF32 压缩请求记录为性能提示，Metal 管理硬件分块及压缩。
- DeviceSetAutomaticCheckpointsMask：本机 release SDK 实现直接返回 true；宿主复现此行为。
- TextureBuilderGetViewOffset：按宿主相同的 Tegra 布局计算 mip 与 layer 的存储偏移。
- TextureGetMemoryPool：SDK 为 `ldr x0,[x0,#0x10];ret`，返回指针。修正参考头文件误写的结构体返回类型，并重新生成 ABI 类型检查表。
- BindProgram：按实际着色器阶段保存状态，宽图形掩码不能把一个 VS 同时留在不存在的 FS/GS/TCS/TES 槽。依据本机 SDK `+0x4c2c00` 的图形包/计算分支及缺失阶段禁用逻辑组合阶段；部分替换保留其他阶段。测试覆盖宽掩码、后续单阶段替换、图形/计算并存及重复阶段拒绝。

## Metal 存储与纹理

NVN 55 的 `NVNtexture` 只有 128 字节，`NVNtextureView` 只有 16 字节。参考版本的 192/40 字节定义会写坏游戏相邻对象。目标构建收紧纹理内部结构到 128 字节，并按本机 SDK 位域编码/解码视图的层、级、目标、格式、通道映射与深度模板模式。测试使用独立 SDK 字节向量及前后 canary；其他目标保留原布局。

映射缓冲使用 Apple silicon 共享内存。Flush/Invalidate 验证范围并使用 release/acquire CPU 内存栅栏；GPU 完成由已有队列与 Sync 接口负责。Metal 层级深度元数据不需要应用分配 ZCull 缓冲，因此对应大小查询为零。

纹理和采样器描述符按底层内存池、偏移和类型建立命名空间；游戏同时使用两个纹理池和两个采样器池，相同局部 ID 不再覆盖彼此。切换当前池会失效 Metal 参数缓存，指向相同存储的池对象共享命名空间。本目标关闭尚未识别池命名空间的 TBDR 前瞻。独立测试覆盖相同 ID 的隔离、存储别名和上界。

命令中的 inline uniform 更新复制到 GPU fence 管理的上传 arena；不能把提交展开后的临时 CPU 字节直接作为异步 GPU 读取源。

纹理 builder 和 view 保存通道映射，查询按原状态返回。采样视图应用 NVN 映射，格式转换的映射先行，view 设置覆盖 builder 设置；渲染附件仍使用底层贴图。NVN 和本机 Metal 的六种通道枚举值逐项一致。

`WriteTexels` 按 Tegra block-linear 地址写入指定区域，保留区域外与其他 mip。GPU 已持有权威内容时，通过同队列 Metal blit 更新该区域。素材的 IMAGE 标志不等于 GPU 已写入；实际绑定为渲染附件、RW image、拷贝目的端后才转为 GPU 权威。不同字节布局的视图重解释尚不支持，会明确中止；不同对象共享同一存储的完整别名一致性仍需实测。

绘制与清除适配包含：GPU `ClearBuffer`、原生 GPU 间接绘制、深度 clamp、固定宽度 1 的线、COPY logic op。其他线宽、非 COPY logic op、启用有损 color reduction 均拒绝。关闭 color reduction 时，其阈值只保存为性能提示。没有用 CPU 读取间接绘制数量替代 GPU 时序。

审计发现上游 `g_nops` 仍把间接计算、批量间接绘制、深度边界和同步等命令注册为空实现。本目标已关闭这些注册，只保留无渲染语义的调试标记；未适配的真实命令回到明确失败。游戏已实际触发 `DispatchComputeIndirect` 和 `MultiDrawElementsIndirectCount`，之前因此漏掉主模型绘制路径。

间接计算直接使用 Metal GPU 参数地址。批量间接绘制先在 GPU 上读取计数和带 stride 的原始记录，夹取计数到 maximum，为剩余槽生成零数量参数，再编码原生间接 draw。保留索引起点、带符号 base vertex 和 base instance，CPU 不读取 GPU 生成的计数或参数。当前 maximum 上限 65535，不支持四边形/几何展开与该间接路径组合。`make test-gpu` 的 8 组真实 GPU 回读覆盖数组/索引、GPU 写计数、夹取、padding、负 base vertex 和写边界。

DepthBounds 比较的是附件里**已有的深度**，而非新片元的 z（参见 [Khronos fragment operations](https://github.khronos.org/Vulkan-Site/spec/latest/chapters/fragops.html) 的存储深度语义）。当前适配先在 GPU 上将深度平面快照到 R32F，片元入口读取相同像素并在任何副作用前拒绝范围外样本；无深度附件时通过。支持单采样、二维、level/layer 0 的 Depth32F（含模板组合格式），其他情况明确失败。批量绘制关闭深度写入时共享一次快照。24 个实际 Metal 测试像素验证与 incoming z 不同的存储值、包含边界、NaN、关闭测试、拒绝后无原子副作用。此保守路径仍需性能优化。

ShaderScratchMemory 验证指定内存范围；Maxwell scratch 分配由 Metal 编译管线的私有线程存储取代，不读取该 Tegra 分配。原请求大小保留诊断，不伪造一套 Maxwell scratch 内容。

允许颜色/深度附件全部为空的实际片元通道：用游戏的 viewport/scissor 定义 Metal 无附件光栅尺寸，保留片元的存储缓冲副作用。Bayonetta 的曝光计算正使用此路径；旧后端会跳过，导致曝光缓冲一直为零，HDR 中已有模型也无法正常合成。严格运行已观察该缓冲恢复非零及人物/场景上屏。另有 3 组实际 Metal 回读验证无附件光栅的 viewport、scissor 和原子写入。未知 MSAA resolve 及超时的队列同步在本目标明确失败。

NVN alpha-test 下沉到本游戏的片元 MSL，使用每次 draw 独立保存的函数/参考值；discard 在片元输出提交之前执行。`make test-gpu` 的实际 Metal 回读覆盖八种比较函数、边界和 NaN，共 32 项。这只是该功能测试，不代表游戏着色器语义全覆盖。

## 着色器版本与生命周期

已观察到同一程序含 GPU code 1.12/1.14/1.15/1.16，控制段分别为 0x838/0x848/0x850/0x880 字节。按声明版本与长度共同验证、哈希和采集，保留游戏原有版本检查。`ProgramSetShaders` 保存控制段与代码的独立快照，防止游戏释放资源档案后延迟绑定读到复用内存。

采集以完整代码先发布、控制段后发布；重启时验证双方长度并修复被中断的采集。打包前校验声明长度、控制段哈希和阶段，零字节代码不会被误判为计算着色器。细分控制/求值阶段会在 `work/shpack/capture_report.json` 明确列出，当前尚不支持。

着色器链包含翻译器、编译器和输入表指纹。运行严格检查链版本与反射；缺失映射/库默认中止。`--capture-shaders` 仅用于继续采集，其省略绘制的结果不能用于可玩验收。`--used-only` 可快速构建实际提交观察过的键；生成的着色器、反射和采集表始终留在被忽略的 `work/`。

记录原始程序的阶段配对发生在加载 metallib 之前，即使缺库失败也保留 VS/FS 的接口需求，供下一轮翻译生成完整 varying。严格模式同步创建 PSO 失败也会中止，不能将缺少绘制的帧记作通过。

资源反射修正 `BufferUsageFlags.Write` 为 bit 0，并从 MSL 图像 access 权限传递写标记。后端据此声明写用途并保持 GPU 图像权威，避免错误地以旧 CPU 数据覆盖写后内容。

## 验证边界

`make test` 的 C 测试检查 deferred 数组在录制后修改能被提交观察、提交冻结后修改不影响记录、40 个纹理句柄分块、UBO 地址/长度以及非法槽位。这里不证明多线程修改同一数组合法，也不证明完整游戏渲染。

着色器捕获和翻译使用独立 `work/shaders`、`work/shdump`、`work/shpack` 及 Metal 缓存；不采用参考游戏的着色器表。翻译器使用本机项目私有 .NET 10 工具链。真正捕获及画面结果以 STATUS.md 的运行证据为准。

图形阶段配对会影响顶点插值导出：Metal 要求片元读取的 user(locnN) 有匹配的顶点输出。`tools/build_shaders.py` 将运行时配对按 VS→FS / VS→GS 边规范化并冻结到被忽略的 `work/shaders/shader_pairs.tsv`；计算阶段状态和重复样本不影响该快照。快照纳入翻译链哈希，编译全过程使用同一份快照；新配对仍需要重新翻译、重建宿主并严格重跑。一次完整着色器编译不证明未来新组合的接口已匹配。

后台管线预测与覆盖探针会临时重放 state_op。Bayonetta 阶段绑定现在属于绘制状态 S，必须随 S 一起回滚；预测同时恢复 R 中的裁剪框。此前独立静态绑定数组泄漏未来程序到当前绘制，造成与缓存命中时序有关的错误 VS/FS 组合。运行时配对日志可能包含前瞻或部分绑定的中间状态，不能仅凭日志认定每一条都是游戏真正绘制的组合。

阶段组合缓存使用开放寻址表，以每阶段的程序指针、序号与着色器索引为完整键，显式生成 uint64 字段，排除结构体填充。此前线性扫描在状态恢复后成为热点；sample 的提交线程 663/719 样本在查找处。C 回归覆盖键的填充无关性与序号/索引隔离；性能结论以实际宿主重跑为准。原生输入脚本支持 `seconds shot /absolute/path.png`，请求在下一真实出图帧采样，便于帧率变化时核对输入。
