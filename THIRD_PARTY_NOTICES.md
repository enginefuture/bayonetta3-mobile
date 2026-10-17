# Third-party notices / 第三方声明

The compatibility-layer source is MIT licensed. Individual third-party components retain their own licenses. No license here grants rights to Bayonetta 3 or any other game's programs, assets, trademarks or keys.

兼容层源码采用 MIT 许可证；第三方组件保留各自许可证。任何源码许可证都不授予对 Bayonetta 3 或其他游戏的程序、资源、商标或密钥的权利。

| Component | Origin / license | Local notice |
|---|---|---|
| Native host and graphics foundation | [blade2-mobile](https://github.com/ha7rock/blade2-mobile), MIT; pinned commit in [UPSTREAM.json](third_party/UPSTREAM.json) | [LICENSE](third_party/blade2-mobile/LICENSE) |
| Original compatibility-layer method and implementation | [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile), MIT, inherited through blade2-mobile | [LICENSE.d2r-mobile](LICENSE.d2r-mobile) |
| Offline shader translation library | Ryujinx Team and Contributors, MIT; used at build time | [LICENSE.txt](third_party/blade2-mobile/dm/third_party/ryujinx/LICENSE.txt) |
| SPIR-V generator | Spv.Generator, MIT | [LICENSE](third_party/blade2-mobile/dm/third_party/ryujinx/src/Spv.Generator/LICENSE) |
| BC texture decompression | bcdec, MIT or Unlicense | [LICENSE](third_party/blade2-mobile/dm/third_party/bcdec/LICENSE) |
| Deflate decompression | libdeflate, MIT | [COPYING](third_party/blade2-mobile/dm/third_party/libdeflate/COPYING) |
| Optional image comparison tooling | NVIDIA FLIP, BSD 3-Clause; bundled headers keep their individual notices | [LICENSE](third_party/blade2-mobile/dm/third_party/flip/LICENSE) |
| NVN interface declarations | h1k421, MIT; adapted for the target ABI | [nvn.h](third_party/blade2-mobile/dm/gfx/nvn/include/nvn.h) |
| Texture layout algorithm | deko3d, zlib; adapted rather than an unmodified copy | [LICENSE.deko3d](LICENSE.deko3d) |

Local source changes are recorded in [docs/UPSTREAM_CHANGES.md](docs/UPSTREAM_CHANGES.md). The published snapshot omits unrelated upstream artwork, UI string tables, shader metadata and application shells; the three generic iOS build helpers are retained. The geometric placeholder icon inherited from blade2-mobile is source-project artwork, not a game extraction.

本项目修改记录见 [docs/UPSTREAM_CHANGES.md](docs/UPSTREAM_CHANGES.md)。公开快照省略无关上游图像、界面文本表、着色器元数据和应用外壳，仅保留三个通用 iOS 构建辅助脚本。继承的几何占位图标属于源码项目图像，不是游戏提取资源。
