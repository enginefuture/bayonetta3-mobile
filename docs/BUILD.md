# Build from your own game files

[简体中文](BUILD.zh-CN.md) · [README](../README.md)

Read the [game files policy](GAME_FILES.md) first. This is a developer workflow for the profiled Switch 1.2.0 release, not a download or one-click installation guide. All commands below run from the repository root. No step requires uploading your files.

## 1. Tools

Tested development environment: Apple silicon, macOS 26.6.2, Xcode 27.0, .NET SDK 10.0.402. Minimum build settings are macOS/iOS 26; older configurations are unverified. Intel Macs and the iOS Simulator are not supported by this workflow.

Install full Xcode and select its developer directory. Ensure the Metal compiler component is available. Check:

```sh
xcodebuild -version
xcrun -sdk macosx metal --version
xcrun -sdk iphoneos metal --version
```

Install Python 3, LLVM, SPIRV-Cross and FFmpeg (Homebrew users can use `brew install python llvm spirv-cross ffmpeg`). Install the **.NET 10 SDK**, not only its runtime, from [Microsoft](https://dotnet.microsoft.com/download/dotnet/10.0). For iOS also install XcodeGen (`brew install xcodegen`). Prepare your own local NSTool executable; development used [NSTool 1.9.2](https://github.com/jakcron/nstool). These tools are separate from the game and no game/key downloads are provided.

```sh
make setup
.venv/bin/python tools/setup_shader_tools.py
```

The helper builds the vendored open-source translator and keeps outputs under `work/`. It uses an existing .NET 10 SDK; `--dotnet /absolute/path/to/dotnet` selects one explicitly. Initial package restore may contact NuGet for software dependencies, never for game data. The helper creates a local SDK symlink and copies SPIRV-Cross for the shader wrappers. It does not download a game, keyset or shader cache.

## 2. Prepare local inputs

Substitute paths to your **own** base NSP, 1.2.0 update, keyset and NSTool. The placeholders below are not files supplied by this project.

```sh
.venv/bin/python tools/prepare.py \
  --base '/absolute/path/to/your/base.nsp' \
  --update '/absolute/path/to/your/update-1.2.0.nsp' \
  --keys '/absolute/path/to/your/prod.keys' \
  --nstool '/absolute/path/to/nstool'
make analyze
make rewrite
make verify
```

Preparation validates PFS0 ranges, selects main Program ID `01004a4010fea000` rather than the other program index, and merges ExeFS/RomFS under `work/game/`. Original inputs are read only. An interrupted extraction keeps diagnostics in `work/game.partial/logs`; `--resume` can reuse complete unpacked members. Do not delete your original inputs to retry.

Rewriting rejects a Build ID/hash mismatch against `config/bayonetta3-1.2.0.json`. Do not remove that guard. Verification needs LLVM, defaulting to `/opt/homebrew/opt/llvm/bin`; for another location run `.venv/bin/python tools/verify.py --llvm-bin /path/to/llvm/bin`. A passing receipt is required to launch, and rewrite file hashes are checked again at launch.

## 3. Prepare movie caches

The tested AVFoundation path does not directly decode the game's VP9/WebM files. Generate local AVC caches from the complete original movie directory, including its tutorial and skill-tree subdirectories:

```sh
.venv/bin/python tools/prepare_media.py work/game/RomFS/movie --jobs 2
.venv/bin/python tools/prepare_media.py work/game/RomFS/movie --check
```

Caches and their inventory stay in `work/media/`. Conversion verifies frame count, dimensions, timing and supported range metadata before atomically publishing each cache and its checksummed receipt. Valid caches are reused on retry. AVC is lossy and image/audio quality still needs inspection. Launch checks every original and cache checksum by default, preventing a later chapter from aborting for an unprepared movie. `--skip-media-preflight` is an explicit diagnostic exception; it does not make missing caches playable. A single original file is also accepted for targeted repair. No game data is downloaded or uploaded.

## 4. Bootstrap your own shaders

No shader library or capture table is distributed. Build a host, then use **diagnostic capture mode** to observe your game's shaders:

```sh
make mac
.venv/bin/python tools/run_mac.py --seconds 120 --capture-shaders
```

Use J/Space to confirm title/menu choices. Capture mode may omit draws when a library is missing, so incomplete/black frames are expected and are **not gameplay validation**. It records shader code, texture facts and stage pairs under private `work/`. The 120-second diagnostic watchdog may exit with code 142; that is a time limit, not a compatibility pass.

Close the host before freezing and compiling capture inputs:

```sh
.venv/bin/python tools/build_shaders.py --jobs 8
make mac
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud
```

The build packs captures, freezes observed stage pairs, fingerprints local tools, translates supported shaders, writes Metal libraries and regenerates the chain header. Rebuilding the host is required because it checks that chain. Run without `--capture-shaders` to validate actual rendering.

New scenes can encounter missing shaders or new vertex/fragment interfaces. Repeat capture → close host → compile → rebuild host → strict run. Capture facts and pairs depend on the path you actually reach; reaching the opening may require several iterations, and later chapters are not verified. `--used-only` compiles just observed submission keys after you have populated `work/shaders/used.txt`. Unsupported tessellation is reported separately and cannot be fixed by ignoring a build error.

## 5. HUD, input and diagnostics

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud-log
```

This enables Apple's Metal HUD and console statistics for the child process. `--seconds 0` keeps the host open; Command-Q or closing the window quits. The default without `--seconds` is a 30-second diagnostic run. Logs are in `work/run/log/`, saves in `work/run/save/`; emulator saves are not used. Keyboard mapping is in the README.

Use `--trace-fs` or `--trace-nvn` when diagnosing a specific failure. Keep logs private and share only a redacted error summary. Do not report capture-mode output or process lifetime as a playable result. Opening-scene HUD figures do not represent combat or whole-game performance.

For combat and chapter-transition diagnostics:

```sh
.venv/bin/python tools/run_mac.py --seconds 0 --metal-hud --profile
.venv/bin/python tools/analyze_run.py work/run/log/native-YOUR-RUN.log
```

Each launch writes a raw `.log`, media `.preflight.json`, `.session.json` (host/shader identity and options), `.events.jsonl`, and an exit `.summary.json`. The parent records native crashes even when the host aborts. Exit summaries distinguish missing media, shader/pipeline failures, native crashes and diagnostic timeouts; none imply gameplay passed. `--profile` adds per-frame `.frames.tsv`, slow-frame diagnostics and depth-copy counts/transfer volume. Frame TSV defaults to a 32 MiB cap (`--profile-log-mib 1..256`); reaching it is logged and ordinary summary windows continue. The analyzer writes a private `.analysis.json`; a capped prefix is not a whole-session performance measurement.

Optional `--gpu-profile --gpu-profile-every 60` records sampled Metal 4 render/compute/blit encoder timestamps in `.passes.tsv` (32 MiB cap). Precise timestamp probes can split encoders and change performance, so use a separate run from FPS comparisons. Encoder spans can overlap and must not be added together. A span of `-1` means no usable timestamp, including empty/clear-only render passes; it does not mean zero GPU cost. All diagnostics and captures remain under ignored `work/`.

The Metal 4 path batches GPU indirect-count preparation across proven read-only command segments. Counts remain GPU-resident; draws, graphics quality and game logic are preserved. Copies, uploads, compute, clears, events, queries, attachment changes, unknown reflection and possible input aliases end a batch. `--indirect-batch 0` selects the original preparation path for comparison. For a same-process diagnostic A/B, pass `--indirect-batch-control work/run/batch-policy.txt`; write `0` or `1` to that local file. It is polled every 60 frames, and changes are logged with a frame number. Keep camera/scene and HUD/probe settings the same, discard transition windows, and compare `@frame_ms`, `@gpu_ms`, `@passes` and `@indirect_batch_*` metrics. Do not compare a precise-probe run with a normal FPS run.

## 6. Experimental iOS builds

Only proceed after completing the Mac capture/strict-run cycle. Compile the observed-path iPhoneOS shaders and make an unsigned build:

```sh
.venv/bin/python tools/build_ios_shaders.py --jobs 8
.venv/bin/python tools/build_ios.py --bundle-id org.example.bayonetta3mobile
```

This generates `platform/ios/Bayonetta3IOS.xcodeproj` and a local App under `work/ios/`. **Unsigned apps cannot be installed.** Source builds do not prove compatibility on a device. Signing/install and on-device gameplay have not been verified for this project.

With your own Xcode account, development team, unique bundle identifier and appropriate entitlements, you can attempt a local signed build:

```sh
.venv/bin/python tools/build_ios.py --sign --team-id YOUR_TEAM_ID \
  --bundle-id YOUR_UNIQUE_BUNDLE_ID
```

Inspect `work/build-ios.log` for provisioning errors. The current shell requests increased-memory and extended-virtual-addressing entitlements; entitlement/account availability and actual device memory limits still need validation. The signing command is not an install command. Do not publish the resulting App/IPA: it contains your rewritten game program and shaders.

For subsequent device experiments, the shell expects your complete RomFS in its container's `Library/Application Support/romfs` and prepared movie cache in `Documents/media`. `core_000.pkz` is the resource marker; copying only that file is insufficient. Logs go to `Documents/boot.txt`. Container transfer, signing and all device behavior remain developer work to verify, not a supported end-user installation promise.

## 7. Source-only tests and publication

```sh
make test
make test-gpu
python3 tools/audit_public.py --all-history
```

The first two use synthetic inputs, not game files. The audit checks Git's staged/index content and, with `--all-history`, reachable historical blobs. Never force-add `work/`, keys, captures, packages or game content. See [CONTRIBUTING.md](../CONTRIBUTING.md).

The shader build now decodes **all captured fragment inputs**, even with `--used-only`, and gives vertex shaders a complete compatible varying interface. It checks the actual generated graphics interfaces and writes a private `_interfaces.json` integrity receipt. Normal Mac startup checks that receipt and the libraries; after a preflight failure, rebuild the shaders and host. This avoids collecting every possible stage pairing merely to link a new scene. Previously uncaptured programs and unsupported tessellation stages remain separate limitations. All receipts and game-derived libraries stay under ignored `work/`.
