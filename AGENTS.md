# Bayonetta 3 Mobile

- This is a native compatibility-layer port. Do not substitute streaming, an emulator launcher, screenshots or a demo scene for actual game execution.
- Keep game programs/assets, keys, tickets, saves, shader dumps and generated executable images under ignored `work/`. Never commit or upload them.
- Version profiles must include the exact NSO build IDs and SHA-256. Never remove a guard to force an unknown build through.
- Keep the upstream commit and license notices. Document changes to vendored code in `docs/UPSTREAM_CHANGES.md`.
- Validate instruction rewrites with independent LLVM structure checks, Unicorn equivalence, and relevant synthetic regressions. These do not prove concurrency or game compatibility.
- Missing services must have a reasoned SDK-level adapter or a visible failure. Never silently return success for unimplemented kernel calls in this target.
- Test the actual host after service changes. Record the first unresolved blocker and current run log in `docs/STATUS.md`.
- Distinguish: source builds, rewrite checks pass, SDK starts, first rendered frame, title interaction, gameplay, signed iOS install, on-device gameplay.
- Never label an unsigned iOS build as installable or either platform as playable without observed evidence.
