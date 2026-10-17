# Contributing / 参与开发

Support legitimate game purchases. Contributions are compatibility-layer source, synthetic tests and documentation only. Read [Game files policy](docs/GAME_FILES.md) / [游戏文件政策](docs/GAME_FILES.zh-CN.md).

支持正版。仅接收兼容层源码、合成测试与文档，不接收游戏文件、密钥、原始/翻译着色器或含游戏内容的安装包。

## Changes / 修改

- Keep exact build fingerprints, unknown-call failures and strict shader checks. Do not bypass them to claim compatibility. / 保留精确版本校验、未知调用失败及严格着色器检查。
- Document modifications to upstream source in `docs/UPSTREAM_CHANGES.md`; preserve all license notices. / 记录上游改动并保留许可证。
- Use synthetic fixtures. Do not copy bytes, shader bodies, assets or saves from a game into tests. / 测试使用合成输入，不复制游戏内容。
- Run `make test`; graphics changes also need `make test-gpu` on a Metal-capable Mac. Actual game/service changes require local host verification. / 按改动运行回归和本地宿主验证。
- State what was observed: build, title, control, combat, signed installation or device gameplay. Do not equate these milestones. / 区分编译、标题、操作、战斗、签名安装与真机运行。

## Before publishing / 发布前

Review `git status` and the exact staged file list. Stage explicit reviewed paths; never force-add private files. Then:

先检查状态和暂存文件清单，只加入审查后的源码，切勿强制加入私有内容。随后运行：

```sh
python3 tools/audit_public.py --all-history
git diff --cached --stat
```

The audit checks actual Git blobs, not just ignore patterns. It rejects private extensions/paths, executable/container signatures, unreviewed binaries, large files, LFS pointers and recognizable credentials; it also checks historical blobs when requested. It does not replace provenance review. No workflow in this project publishes compiled game-containing artifacts.

审计检查真实 Git 对象而非只看忽略规则，拒绝私有扩展名/目录、程序/容器签名、未审查二进制、大文件、LFS 指针及可识别凭据，并可检查历史；这不替代来源审查。项目 CI 不上传含游戏内容的构建产物。

## Reports / 报告问题

Include hardware, OS, Xcode/tool versions, the supported version fingerprint, exact command and a short redacted error summary. Do not attach complete logs, screenshots containing private information, archives, memory dumps or keys. No requests for game downloads or shared keys.

请提供硬件、系统、工具版本、支持版本指纹、执行命令与简短脱敏错误摘要，不上传完整日志、含隐私截图、归档、内存转储或密钥。不接受游戏下载和密钥分享请求。
