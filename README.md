# Bayonetta 3 Mobile

English | [简体中文](README.zh-CN.md)

An experimental, open-source native compatibility layer for running your own Nintendo Switch copy of **Bayonetta 3** on Apple silicon macOS, with actual iPhone Air gameplay now verified. Built on [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) and [blade2-mobile](https://github.com/ha7rock/blade2-mobile).

> **Support the original game. Buy a legitimate copy. Bring your own game files.**
>
> This repository provides compatibility-layer source code, build tools and tutorials only. **We do not provide, host, link to, or accept NSP/XCI/NSZ files, keys, tickets, game executables, extracted assets, original or translated game shaders, or packages containing game content.** Prepare your own files from a copy you legally own, where permitted. Do not upload them to GitHub, Issues, pull requests, Releases or Actions artifacts. No game downloads or game-sharing support is offered. See [Game files policy](docs/GAME_FILES.md).

This is an independent community project, not an official port and not affiliated with or endorsed by Nintendo, PlatinumGames or SEGA. Game names and trademarks belong to their respective owners. The source license does not license the game.

## Current status

Developer observations as of **2026-10-17**; a research preview, not a finished port.

| Area | What has actually been verified |
|---|---|
| macOS, Apple silicon | Native startup, title/menu, real combat and user-confirmed progression into a new scene; controller operation confirmed |
| NVN / graphics | Targeted NVN **55.12**, Metal rendering and a corpus-wide shader interface covering 2,045 vertex / 4,285 fragment programs |
| Performance | On M3 Max, in-process ON → OFF → ON testing measured about **60 → 18 → 60 FPS** in combat. The later scene run passed 181 new stage pairs without fatal pipeline errors. See [performance measurements](docs/PERFORMANCE.md); this is not a whole-game benchmark |
| iOS / iPhone | Actual combat on iPhone Air (A19 Pro, iOS 27.2); user-confirmed audio, expanded-FOV full screen and HUD. The same app now offers Normal/Wide, Metal HUD and MetalFX launch settings. See [phone support](docs/IOS.md) |
| Still unverified | Complete chapters, long-term stability, audio quality, save round trips, all rendering paths and device lifecycle |

Known issues include material/hair/transparency artifacts, performance variation, and incomplete tessellation coverage. All 2,045 vertex libraries passed real Metal pipeline creation against the complete varying interface, and an approximately 11-minute native scene test exited normally. The complete current ordinary corpus contains 6,408 stages and 860 fragment variants. The private tessellation supplement compiles five original TCS, all six TES and 25 candidate vertex captures. Guarded subgroup lowering preserves the two previously failing TES; all six pass actual Metal pipeline creation. Independent mip/cube uploads and region-write tests pass. This does not establish complete shader or game compatibility. Local evidence paths and limitations are recorded in [STATUS.md](docs/STATUS.md); private logs and captures are intentionally not published.

Native VS → TCS → Metal tessellator → TES execution now passes the previously failing scene. The user confirmed entry and normal visuals with fixed 1080p and MetalFX spatial 4K enabled. Six synthetic GPU cases cover indexed/array draws, instance offsets, vertex divisors, empty scissor and displaced depth. Broader scene coverage remains pending; game frame generation is experimental and off by default. See [graphics implementation and limits](docs/GRAPHICS.md).

The results-screen magenta blocks and smoke corruption were traced to an ignored packaged-texture row-alignment parameter. CPU/GPU upload, mip offsets and region writes now share the corrected layout. Independent ASTC decoding and production GPU tests pass; the user confirmed that the magenta blocks disappeared and smoke returned to normal. Other material artifacts still need separate verification.

## Phone support

- **Verified device: iPhone Air, A19 Pro GPU, iOS 27.2.** A development-signed build runs real combat. Other iPhones and iPads are unverified; the deployment target is not a device-compatibility claim.
- **One app, selectable startup settings:** choose the original 16:9 view or expanded-FOV wide mode, independently toggle Metal HUD and MetalFX, then tap **Play**. Settings persist and can be changed when reopening the app. No second app is needed.
- **Mobile-specific scaling:** normal mode keeps the original handheld picture; the tested wide profile renders at 1568×720, preserves vertical FOV and adapts the HUD. MetalFX targets the phone's native display rather than the Mac's fixed 4K output. iOS frame generation is off.
- **Build and limits:** iOS 26+ is the minimum project target. Local development signing and memory entitlements are required. Heavy effects still reduce frame rate; complete chapters and sustained thermal behavior remain unverified. Read the [bilingual device guide and acceptance scope](docs/IOS.md).

Only source and tutorials are published. No NSP, keys or game-containing IPA is provided. Support the original game and prepare your own files.

## How it works

```mermaid
flowchart LR
    A["Your own game files — local only"] --> B["Exact version checks"]
    B --> C["Offline AArch64 instruction rewriting"]
    B --> D["Local shader capture and offline translation"]
    C --> E["Native host and Horizon service adapters"]
    D --> F["NVN 55.12 to Metal"]
    E --> G["macOS / experimental iOS shell"]
    F --> G
```

The game program runs as rewritten native ARM64 code. The host supplies its platform services, and the graphics layer implements the required NVN operations using Metal. Ryujinx's MIT-licensed shader translation library is used **offline at build time**; the Ryujinx emulator application is not required to run this host. Videos are decoded locally from caches you generate from your own originals.

Only the profiled **Switch version 1.2.0**, Program ID `01004a4010fea000`, is currently accepted. Build IDs and SHA-256 checks reject mismatched modules. Unknown calls and missing shaders fail visibly in the default strict mode. Read the [implementation analysis](docs/ARCHITECTURE.md) for the changes and their limits.

## Build and run

You need an Apple silicon Mac, macOS 26+, a full Xcode installation with its Metal toolchain, Python, LLVM, .NET 10, SPIRV-Cross, FFmpeg and your own local game files. The tested development environment uses Xcode 27; older systems/toolchains are not verified.

```sh
git clone https://github.com/enginefuture/bayonetta3-mobile.git
cd bayonetta3-mobile
make setup
```

Continue with the **[English build tutorial](docs/BUILD.md)** or **[中文构建教程](docs/BUILD.zh-CN.md)**. They cover local preparation, rewriting and verification, building the shader translator from source, the capture/compile/strict-run cycle, Metal HUD, and experimental iOS builds. A fresh clone contains no prebuilt game program or shader cache; it is not ready to run until you complete those steps.

After preparing and validating your local workspace:

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud
```

`0` disables the diagnostic time limit. Close the window or press Command-Q to quit. Add `--metal-hud-log` to record HUD statistics in the private run log.

| Keyboard | Switch input |
|---|---|
| WASD | Left stick |
| J / Space, K, U, I | A, B, X, Y |
| Q / E, Z / C | L / R, ZL / ZR |
| Arrow keys | D-pad |
| Return / Tab | Plus / Minus |

## Project layout

| Path | Purpose |
|---|---|
| `tools/` | Local preparation, module checks, build and launch wrappers |
| `config/` | Version fingerprints and interface names, no game bytes |
| `platform/ios/` | Experimental UIKit/Metal shell and project specification |
| `tests/` | Synthetic rewrite, ABI and GPU regression tests |
| `third_party/` | Pinned upstream source and third-party licenses |
| `docs/` | Tutorials, architecture, observed status and upstream changes |
| `work/` | **Private and Git-ignored**: all game inputs, keys, saves, generated outputs and run evidence |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Reports should include your OS, hardware, tool versions and a redacted error summary. Never attach game data or keys. Tests that do not require game files:

```sh
make test
make test-gpu  # Apple silicon Mac with Metal
```

Before publishing changes, stage only reviewed source files and run `python3 tools/audit_public.py --all-history`. CI repeats the source-content audit. `.gitignore` is one guard; the audit also checks the actual Git index/history, including force-added files. It cannot establish legal provenance of every byte, so contributors must still review what they submit.

## Credits and license

Compatibility-layer code is available under the [MIT License](LICENSE), with original notices retained. The host/graphics foundation is vendored from blade2-mobile commit `c981fcb62fe9962ca81d359f639bd05117bd03b4`, inheriting d2r-mobile's method and code. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [UPSTREAM.json](third_party/UPSTREAM.json), [upstream changes](docs/UPSTREAM_CHANGES.md) and [interface metadata inventory](docs/DERIVED.md).

**No NSP files. No keys. No game assets. No game-containing downloads. Support legitimate purchases.**
