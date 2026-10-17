# Interface metadata / 接口元数据

This inventory distinguishes interface descriptions from executable game content. It follows the documentation approach of d2r-mobile; it does not extend any license to game content.

本清单参考 d2r-mobile 的文档组织方式，区分接口描述与游戏内容，不扩大对游戏内容的任何授权。

| Published item / 公开内容 | Purpose / 用途 |
|---|---|
| `config/bayonetta3-1.2.0.json` | Title/Program ID, module Build IDs and SHA-256 fingerprints; reject an unverified version. No module bytes. / 版本校验指纹，不含模块字节。 |
| `config/nvn55-names.txt`, `nvn_slots.tsv` | Graphics function names and dispatch ordering. / 图形接口名与分发表顺序。 |
| `nvn55_api.inc`, `nvn55_snapshot.h`, object/view/control headers | Independently implemented wrappers and observed ABI sizes, offsets and signatures. No extracted SDK machine code. / 独立实现的适配器及 ABI 结构，不含 SDK 机器码。 |
| Guarded graphics profiles and independent checks | Exact-build offsets, small configuration/math instruction guards and independent LLVM/Unicorn tests for resolution/camera interoperability; no complete game program or shader. / 为分辨率/相机互操作而编写的偏移、少量配置/数学指令守卫及独立验证，不含完整游戏程序或着色器。 |
| Host service adapters | Symbol names, argument layouts and independently written platform behavior. / 服务符号、参数布局及宿主实现。 |
| `docs/VALIDATION.json`, status and change notes | Hashes, numeric observations, shader identifiers and private evidence path references; the evidence files themselves are excluded. / 哈希、数值、着色器标识和私有证据路径，不含证据文件。 |
| Upstream source | MIT/BSD/zlib code, interface declarations, historical notes and synthetic tests retained with notices. / 保留许可声明的上游源码、接口声明、历史说明和合成测试。 |

All Bayonetta shader captures, shader code/translations, reflection/texture-fact/pair tables, rewritten images and game resources are produced locally under ignored `work/`. Unrelated upstream shader tables, game UI text tables, art and shells are omitted from the published snapshot. Compatibility changes are documented in [UPSTREAM_CHANGES.md](UPSTREAM_CHANGES.md).

所有 Bayonetta 着色器采集、代码/翻译、反射/纹理事实/阶段配对表、改写映像和游戏资源均在本地忽略目录 `work/` 生成。公开快照排除无关上游着色器表、游戏界面文本表、图像及应用外壳。源码改动见 [UPSTREAM_CHANGES.md](UPSTREAM_CHANGES.md)。
