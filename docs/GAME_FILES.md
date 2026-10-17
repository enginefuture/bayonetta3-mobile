# Game files: bring your own

[简体中文](GAME_FILES.zh-CN.md) · [README](../README.md)

**Buy Bayonetta 3 and support its creators. This project supplies no game content.** Use your own legally owned copy and comply with the rules that apply to your use. This policy describes what the project accepts; it does not promise that ownership permits every extraction or use in every jurisdiction.

## What you need locally

- Your own Switch base-game dump and the update matching the supported 1.2.0 fingerprint.
- Your own locally obtained keyset required by your extraction tool. Never send keys to maintainers.
- A local extraction tool such as NSTool (development used 1.9.2). It is not a source of game files.

The tutorial begins with files you already have. It does not describe obtaining files from third-party download sites, sharing credentials, or acquiring someone else's keys. There is no game-content download feature in this port.

`tools/prepare.py` reads the paths you explicitly supply, selects the main Program ID and merges base/update contents into the private workspace. It does not search an emulator's directories automatically, modify emulator settings or touch emulator saves. Ryujinx is not a runtime dependency.

## What must never be published

| Private content | Includes |
|---|---|
| Distribution files | NSP, NSZ, XCI, XCZ, NCA, tickets and certificates |
| Executable content | NSO/ExeFS, decompressed images, rewritten binaries and embedded-image assembly |
| Resources | RomFS, PKZ/PAK archives, textures, audio, videos and transcoded movie caches |
| Game shaders | Original captures, packed shaders, SPIR-V/MSL translations, compiled Metal libraries and per-game generated reflection/cache tables |
| Personal material | Keys, credentials, signing identities, provisioning profiles and saves |
| Packages | App/IPA/archive files containing any of the above |

The local iOS build embeds your rewritten game modules and shaders. **Do not upload that App or IPA as a release**, even if you kept RomFS separate. The open-source license covers compatibility-layer code, not those modules.

Keep private material under ignored `work/`; source NSP/key inputs may instead remain outside the checkout. Do not copy private files into examples or test fixtures. The same rule applies to Git history, LFS, Issues, comments, PR attachments, Releases, Actions caches and artifacts. Share only small redacted diagnostic summaries, not whole run folders or dumps.

## What is published

Source code, synthetic tests, tutorials, license notices, version fingerprints and limited interface descriptions. [DERIVED.md](DERIVED.md) inventories interface metadata. No original program bytes or shader bodies are included. `.gitignore`, a staged/history audit and CI help enforce this boundary; review is still required.

If a contribution accidentally includes private material, stop publication, remove it from pending changes/history and rotate exposed credentials as appropriate. Do not quote or repost the sensitive contents in a public report.
