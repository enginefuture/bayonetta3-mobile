# Implementation analysis

[简体中文](ARCHITECTURE.zh-CN.md) · [README](../README.md)

The implementation combines a version-locked offline program rewriter, native Horizon service adapters and an NVN-to-Metal graphics backend. The game logic is supplied by the user's original program. There is no streaming service or emulator-application launcher in the runtime path.

| Layer | Implementation | Current assessment |
|---|---|---|
| Local preparation | `tools/prepare.py` checks bounded PFS0 entries, selects Program ID, merges base/update with local NSTool | Produces private ExeFS/RomFS; no download mechanism |
| Program rewriting | `tools/rewrite.py` gates upstream `patch_nso.py` on exact Build ID/SHA-256 | Rewrites system calls, thread registers, timers and Apple ABI conflicts; runtime loads `main`, `subsdk0`, `sdk` |
| Verification | LLVM structural checks and randomized Unicorn equivalence plus mutation controls | Necessary checks, not proof of concurrency: the harness replaces exclusive accesses on both sides |
| Native host | Generic upstream loader, memory/thread/filesystem/input/audio/movie services and `hle_bayonetta3.c` | Handles observed SDK calls; unsupported calls must fail visibly |
| NVN 55.12 | ABI wrappers, texture objects/views, descriptors, deferred state and command submission | Target-specific subset, not a complete NVN implementation |
| Shaders | Local capture → Ryujinx translation library → SPIR-V → SPIRV-Cross MSL → Apple Metal compiler | Offline translation; generated code and caches remain private |
| macOS | Cocoa window, CAMetalLayer, keyboard/controller mapping, isolated saves | Opening and basic control observed; full gameplay remains unverified |
| iOS | UIKit shell, embedded rewritten modules, Metal libraries and virtual controller | Builds unsigned; signed install and device behavior unverified |

## Changes needed for this game

The inherited driver used an earlier NVN ABI. This target requires 128-byte texture objects, 16-byte views, multiple GPU control-record lengths, corrected descriptor namespaces, and submission-time snapshots of deferred bindings. The port also implements indirect compute, GPU-counted indirect draws, alpha comparison, stored-depth bounds, swizzle/mip regions and attachmentless fragment passes. Restoring the last of these recovered the exposure-buffer writes needed for visible 3D output.

Background pipeline prediction originally leaked future shader bindings and scissor state into current draws. Stage bindings now travel with the saved draw state, and raster state is restored. Shader combination lookup uses canonical full-identity hash keys rather than a linear scan. Frozen stage-pair snapshots participate in the shader chain fingerprint so newly observed interfaces cannot silently reuse an old cache.

Movie-service overloads are adapted to the observed ABI. Since the tested AVFoundation path could not decode these VP9 originals directly, users generate private AVC caches; the host still decodes real frames and preserves the original timeline. AVC conversion is lossy and is not a visual-equivalence claim.

## What the evidence supports

Mac observations establish title interaction, real-time opening rendering and basic movement/action feedback. Metal HUD samples show selected opening intervals near 60 FPS and GPU medians around 11–12 ms, with drops and a long pause also recorded. The test suite covers synthetic rewrite patterns, service buffer boundaries, NVN layouts/deferred bindings, texture regions, alpha/depth operations, indirect preparation and attachmentless writes.

Those checks do not establish complete combat, later chapters, audio correctness, save round trips or all rendering paths. Tessellation remains unsupported, and material/hair/transparency defects remain. Unsigned iOS compilation establishes only a build result; provisioning, memory/address limits, GPU behavior, input and lifecycle still require device testing.

See [NVN55.md](NVN55.md) for detailed semantics, [UPSTREAM_CHANGES.md](UPSTREAM_CHANGES.md) for the modification ledger, and [STATUS.md](STATUS.md) for dated local observations. The latter documents private evidence paths; those files are not part of the public repository.
