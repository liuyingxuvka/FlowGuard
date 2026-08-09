## Why

The existing v0.68.9 change was marked complete even though its final parent validation was only a static child result, the project adoption record still pointed at the older engine, and the current model inventory had moved without a corresponding accepted revision set. The portable DNA envelope also duplicates large identity and binding payloads even though the canonical model directory is the real authority. This correction makes the already-intended v0.68.9 behavior truthful, current, and cheaper to exchange without creating a second DNA authority or changing the release number.

## What Changes

- Repair the current model-authority pointer through the native ModelRevisionSet pipeline, with fresh evidence for every affected owner.
- Treat the canonical model directory as the exchangeable DNA; keep the single-file envelope optional and add a directory-first export/read path that does not materialize a duplicated mega-file.
- Close model-to-code and model-to-test bindings with explicit coverage and execution status, preserving typed gaps instead of claiming a parent pass.
- Reduce duplicated prompt/route material and remove only wrappers or branches whose current contract proof is complete; retain unresolved candidates visibly.
- Deduplicate portable shard references and reject duplicate or stale directory entries without adding compatibility readers or fallbacks.
- Refresh the installed consumer projection and project adoption record at 0.68.9, run affected checks once, then one foreground final parent validation.
- Finalize the existing `v0.68.9` GitHub tag/release identity; do not create `v0.68.10`.

## Capabilities

### New Capabilities

- `directory-first-dna`: Export and verify the canonical model directory as the portable DNA representation, with manifest and shard references but no required monolithic bundle.

### Modified Capabilities

None. Existing portable-DNA, model-authority, model-test-alignment, and
architecture-reduction requirements already define the required behavior; this
change supplies the missing implementation and current evidence for them.

## Impact

- Affected code: `flowguard/portable_blueprint.py`, `flowguard/implementation_blueprint.py`, CLI export/verify routes, model revision/validation orchestration, and focused tests.
- Affected project records: `.flowguard/project.toml`, `AGENTS.md`, adoption log, OpenSpec change artifacts, and release evidence.
- No production target software is reconstructed; no independent reconstruction tool is added; no compatibility authority or fallback reader is introduced.
