## Context

The current release proved that the package, public CI, and GitHub release can be aligned, but the user's broader maintenance objective still includes operational surfaces that are not finished: OpenSpec specs are valid but many purpose headers are placeholders, deep model regression is manual, shadow sync relies on hand-written copy commands, the API registry is still too broad for first-contact agent use, field bloat has no generated ledger, and some large modules remain hard to reason about.

The repository also has two evidence layers: tracked public source and local `.flowguard` model artifacts. A release can be correct in GitHub while local model evidence is stale unless both layers are explicitly checked.

## Goals / Non-Goals

**Goals:**
- Turn recurring local maintenance steps into tracked commands or generated artifacts.
- Keep public APIs stable while adding compact route-first entry points.
- Make field and module bloat visible before future deletion or deeper splitting.
- Split one oversized module responsibility in a behavior-preserving way and document the pattern for future modules.
- Keep release evidence tied to current local install, shadow install, OpenSpec, FlowGuard models, tests, Git, GitHub release, and CI.

**Non-Goals:**
- Do not delete public API names in this change.
- Do not rewrite every large module in one risky movement.
- Do not replace FlowGuard models with a new framework.
- Do not mirror-delete the shadow workspace or overwrite unrelated peer-agent work.

## Decisions

1. **Add tracked runners before broad release claims.**
   - Decision: add a Python aggregate runner that discovers every present `.flowguard/**/run_checks.py` and reports pass/fail in text or JSON.
   - Rationale: ignored local model artifacts can drift from tracked code; a tracked runner makes the check repeatable.
   - Alternative rejected: rely only on GitHub CI. GitHub cannot see all local ignored model artifacts.

2. **Use no-delete shadow sync by default.**
   - Decision: add a shadow sync helper that copies whole source sets and verifies imports, but does not delete shadow-only files unless explicitly extended later.
   - Rationale: the user has parallel AI work; no-delete sync avoids wiping unrelated files.
   - Alternative rejected: mirror sync with deletion. It is faster but unsafe in a shared workspace.

3. **Expose a compact agent-default API without removing the full API.**
   - Decision: add `AGENT_DEFAULT_API` and include it in `API_SURFACE`.
   - Rationale: agents get a small first-read surface while advanced routes keep full helper access.
   - Alternative rejected: remove exports immediately. That would be a breaking change and risks stale downstream imports.

4. **Generate field inventory instead of deleting fields by text search.**
   - Decision: add a dataclass field inventory generator and generated docs artifact.
   - Rationale: redundant-looking fields can be behavior-bearing, compatibility-bearing, or evidence-bearing; deletion needs ownership and lifecycle clues first.
   - Alternative rejected: bulk delete fields based on name patterns.

5. **Split source-audit responsibility out of Model-Test Alignment first.**
   - Decision: move source-code audit helpers into a dedicated module and re-export them from the original public surface.
   - Rationale: this is a coherent responsibility block with stable tests and low public API risk.
   - Alternative rejected: split `ui_structure.py` first. It is larger, but its UI journey contracts are more intertwined and need a separate model-backed split.

## Risks / Trade-offs

- **Risk: helper scripts create false confidence if not run in release flow.** Mitigation: wire them into CI/deep checks and release tasks.
- **Risk: generated field inventory becomes stale.** Mitigation: include regeneration in validation and tests.
- **Risk: module split introduces circular imports.** Mitigation: source-audit module imports already-defined contracts only after Model-Test Alignment has declared them, and tests verify original public imports.
- **Risk: shadow sync overwrites peer work.** Mitigation: no-delete default and explicit source-set copying.
