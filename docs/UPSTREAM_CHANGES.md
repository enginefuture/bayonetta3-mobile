# 与参考源码的区别

参考快照：blade2-mobile `c981fcb62fe9962ca81d359f639bd05117bd03b4`（2026-10-16），完整保留原 MIT 与 d2r-mobile 版权声明。

1. 新增 `dm/host/Makefile.bayonetta3`：本游戏程序 ID、产品名称、`core_000.pkz` 资源标记、通用宿主和缺失导入中止配置。没有启用 D2R 固定地址功能。
2. `dm/gfx/nvn/nvn_mtl.m`：`g_shmap` 字典值类型由 `NSArray *` 修正为实际存储和读取的 `NSString *`，解决 Xcode 27 的 ARC 类型错误。
3. `dm/host/hle.c`：仅在 `DM_UNIMPL_ABORT` 定义时，未实现导入被调用即中止，保留名称和参数。
4. `dm/tools/patch_nso.py`：独占窗口匹配同一访存基址的前向或反向存储，并扩展窗口涵盖内部入口的直接分支；保留窗口内分支，超大区域拒绝。支持窗口内无条件分支重定位。动态 `mov sp,x18` 从旧栈恢复临时寄存器，不依赖新旧 SP 固定差值。
5. `dm/verify/equiv.py`：将独占存储转普通存储时，`CBNZ status` 按成功落下，`CBZ status` 按成功跳转。原实现统一改 NOP，不能覆盖反向 CAS 布局。此测试替换仍不能证明独占监视器/并发语义。
6. `platform/ios`：从上游 `dm/ios/blade` 派生，改为本游戏标题与资源判据，加载并内嵌三个模块；保留上游通用虚拟手柄。构建脚本位于本项目 `tools/build_ios.py`，不使用 Blade II 的路径或着色器表。

未添加游戏逻辑剪口，没有套用 Blade II 或 D2R 的固定地址、游戏存档、着色器包或游戏专属参数。

7. `dm/verify/structck.py`：为 `mov sp,x18` 增加完整指令模板核对，验证旧 SP 保存、槽读取、临时寄存器恢复与出口；不放宽其他块的检查。
8. `dm/host/{loader.c,hle.c}`：未定义 ELF 弱符号在游戏模块及 HLE 表均无实现时解析为零。SDK 13 的可选异常栈回调据此正确走默认路径；实测占位导入从 7 降至 0。
9. `dm/host/hle_svc.c`：Bayonetta 构建的未实现 SVC 中止并记录参数，不继承上游的默认成功结果。
10. 新增 `dm/host/hle_bayonetta3.c`：本地语言码转换、宿主调度下 CPU boost 请求适配、无结果参数的手柄选择器重载。只在 `DM_BAYONETTA3` 下启用。

11. `dm/host/hle_bayonetta3.c`：按 SDK 实际写入范围提供未连接 USB 键盘（0x30）/ 鼠标（0x28）状态；Mac 键盘仍映射到 Npad。增加 canary 缓冲边界测试。
12. `dm/host/hle_fs.c`：补齐不带读取长度指针的 ReadFile 重载，委托同一 pread/脏页处理实现；短读明确中止，不让 fd 被原 SDK 当作 FileAccessor 指针解引用。
13. `dm/gfx/nvn/hle_nvn.c`、`nvn55_api.inc`、`nvn55_snapshot.h`：按本机 NVN 55 SDK 语义实现 deferred 绑定、查询、纹理区域写入及新增绘制状态；提交前冻结 deferred CPU 数组。名字表扩展到 534 个，重新生成原型检查及跳板。未实现调用在本目标中止。细节和不支持路径见 `NVN55.md`。

14. `dm/gfx/nvn/hle_nvn.c`：完成目标接口子集适配后，本目标报告 55.12；其他目标继续原版本。保留游戏 major=55、minor>=12 检查，未知功能仍明确失败，不宣称实现完整 NVN 55 驱动。
15. `dm/gfx/nvn/{include/nvn.h,nvn_obj.h,nvn_tex.h,nvn_view.h}`：目标纹理对象/视图改为 128/16 字节，修复跨对象覆盖，视图使用本机 SDK 位域；其他目标布局不变。修正 Texture/TextureBuilderGetMemoryPool 的指针返回 ABI。
16. `dm/gfx/nvn/{hle_nvn.c,nvn_control.h,nvn_mtl.m}`：识别 GPU code 1.12/14/15/16 的不同控制段长度；ProgramSetShaders 深复制代码/控制段，修复资源复用后的延迟绑定。着色器采集使用原子发布并修复截断文件。
17. `dm/gfx/nvn/{nvn55_texels.h,nvn_mtl.m}`：纹理区域写入、实际 GPU 写入后的素材权威切换、压缩素材 IMAGE 标志处理、格式/swizzle/深度模板视图、GPU buffer clear、间接绘制、深度 clamp、alpha-test 状态快照。非 COPY logic op、非 1.0 线宽及启用有损 color reduction 明确拒绝。
18. `dm/gfx/tools/{dmsh_from_dump.py,nvn_capture.py,dmsh_build.py,dmsh_chain.py,dmsh_facts.py,title_alpha.py}`：使用本游戏独立输入表和缓存；采集长度/阶段校验、细分阶段报告、变量控制段哈希、片元 alpha-test 下沉、缓存指纹包含下沉源码、逐项构建失败报告。没有复用其他游戏的着色器结果。
19. `dm/host/{hle_bayonetta3.c,hle_audio.c,hle_blade.c,hle_account.c,hle_fs.c}`：真实 CoreAudio 输出的新 SDK 重载及缓冲事件、设备增益、单次触屏快照、pushed user 上下文、当前应用保存目录查询与挂载重载。离线 PREPO 返回不可用，不写外部遥测。
20. `dm/host/Makefile.bayonetta3`：增加依赖文件和独立对象目录以增量编译；使用实际 Metal 4 encoder 协议声明，修复间接绘制方法类型检查。
21. `dm/gfx/nvn/{nvn55_descriptors.h,nvn_obj.h,hle_nvn.c,nvn_mtl.m}`：按描述符底层存储建立命名空间，处理游戏多纹理/采样器池的相同局部 ID；切池失效参数缓存，关闭尚未理解命名空间的 TBDR 前瞻。inline UBO 更新保存至 GPU fence 管理的上传 arena。
22. `dm/gfx/nvn/nvn_mtl.m`：加载库前记录实际原始阶段配对，使失败路径也能补齐 varying；严格模式缺顶点阶段或同步 PSO 创建失败中止。
23. `dm/host/{hle_movie.c,movie_av.m}`：根据本地 subsdk0 重定位虚表核对 Bayonetta movie ABI，适配 CacheSize 构造、reader-backed 源、Buffer 构造、缓冲区范围和逐帧 NV12 格式。VP9 原片在私有缓存转 AVC，保持游戏原始 MIME 与时间轴，由 AVFoundation 实际解码。小栈游戏线程的 AV 资源索引移至宿主 GCD 工作栈；未知虚方法保留失败。
24. `dm/gfx/nvn/{hle_nvn.c,nvn55_api.inc,nvn_obj.h,nvn_mtl.m,nvn55_indirect.h}`：关闭目标中的上游 GPU 命令空实现，接入 GPU 间接计算和 GPU 计数批量间接绘制，避免漏掉主模型路径；scratch 交由 Metal 管理并校验请求范围。尚未实现的真实命令明确失败。
25. `dm/gfx/nvn/nvn55_program_bind.h`：本机 SDK 阶段绑定语义、缺失阶段禁用及部分替换；不将单 VS 别名留到其他阶段。独立 C 回归验证图形/计算并存。
26. `dm/gfx/{nvn/nvn_mtl.m,tools/title_alpha.py}`：NVN DepthBounds 读取 GPU 存储深度快照，在片元入口拒绝；非 incoming-z 替代。限定单采样二维 Depth32F 基层，其他路径中止，GPU 24 像素与副作用回读通过。
27. `dm/gfx/{tools/dmsh_build.py,nvn/nvn_refl.m}`：修正缓冲 Write 位（bit 0）及图像写访问反射到运行时，增加真实翻译资源/MSL fixture 回归。
28. `dm/gfx/nvn/nvn_mtl.m`：支持无颜色/深度附件的片元通道，按游戏 viewport/scissor 设置 Metal raster extent，保留曝光计算等缓冲写入。3 组 GPU 回读及真实游戏非零曝光/人物场景上屏验证。增加诊断帧的 GPU 完成后间接参数/小缓冲读回与深度数据导出；诊断数据留在 work。
29. `dm/host/front_mac.m`：本地 NSEvent 诊断脚本支持 `秒 keyhold 键码,时长`，验证持续摇杆输入；按下/松开仍走真实窗口事件与 Npad 通路。

上述改动有服务缓冲 canary、deferred 时序、NVN55 对象/视图字节向量、纹理区域保留及独立 Metal alpha-test 回读验证。完整游戏和 iOS 真机仍按 `STATUS.md` 逐级验收。

30. 翻译链加入规范化图形阶段配对快照，修复原先新增 VS/FS 插值接口仍共用旧链号的问题；冻结输入避免采集与构建并行时出现未记录的配对变化。

31. 修复目标后台 PSO 前瞻状态污染：阶段绑定移入 S，随绘制状态快照还原；前瞻恢复 R（含裁剪框），避免未来程序/裁剪状态泄漏到当前绘制。

32. 阶段组合线性扫描替换为规范化完整身份哈希键；补充 padding/代际/索引隔离测试。原生诊断脚本增加定时实际帧采样，保留实际 NSEvent 输入路径。

33. iOS 工程生成器读取增量 Makefile 的全部 clang 编译及链接命令，修复仅取第一条导致 main.c / 其他源和框架遗漏；保留单命令构建兼容并增加两项生产解析器回归。NVN 提交可读性查询改用 Mac/iOS 共用的公开 vm_region_64，保留保护和范围检查。
34. iOS 壳配置 Documents/media 缓存及实际音视频；新增冻结 Mac 链的 iphoneos 着色器构建包装，iOS 源码构建核对改写回执并支持现有账号的开发签名。507 基础着色器及 95 变体已编译，未签名构建成功；签名因本机账号/描述文件缺失而失败。

35. 公开源码快照不包含无关上游 `dm/data`、`dm/i18n`、iOS 图像/外壳/测试、旧着色器元数据及 `verify/logicself`。仅保留实际使用的 `gen_build.py`、`gen_embed.py`、`ios_metal.py` 三个 iOS 辅助脚本，保留各第三方源码许可；本地原文件未删除。新增中英文实现/构建/自备文件文档、源码对象审计和不上传游戏产物的 CI。/ The public source snapshot omits unrelated upstream assets/shells/game tables while retaining the three required iOS helpers and original source licenses; local originals are preserved.
