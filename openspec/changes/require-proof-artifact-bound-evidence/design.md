## Context

FlowGuard's route text already says that parent model confidence requires
parent coverage, child disjointness, current child reattachment, leaf boundary
matrix evidence, same-class model-miss proof, and a final Risk Evidence Ledger.
The weak point is the evidence object boundary. Several consumers accept a
caller-provided status/current pair, so a project matrix can describe proof as
`passed` without carrying the run artifact that made it true.

The change is cross-cutting because layered proof, model-miss gates, risk
ledger, model-test alignment, and development-process freshness all consume or
produce evidence records. The implementation must stay standard-library only
and preserve existing helper APIs for non-strict/advisory uses.

## Goals / Non-Goals

**Goals:**

- Introduce one reusable proof artifact reference shape.
- Make strict closure reject declaration-only evidence.
- Keep matrices as obligation maps, not sources of truth for pass status.
- Let parent/child proof and model-miss closure express old-path disposition.
- Preserve backward compatibility for existing non-strict helper calls.
- Update package tests, docs, templates, and installed skills.

**Non-Goals:**

- Do not make FlowGuard execute arbitrary project commands from review helpers.
- Do not replace TestMesh, Model-Test Alignment, ModelMesh, or
  DevelopmentProcessFlow.
- Do not make every advisory report require proof artifacts.
- Do not publish a GitHub release in this task unless explicitly requested.

## Decisions

1. **Add `ProofArtifactRef` as the shared evidence carrier.**
   It records `artifact_id`, command, result path, exit code, status,
   timestamps, artifact fingerprints, covered obligation ids, producer route,
   freshness flags, and scope. Review helpers inspect this object; callers are
   still responsible for producing it from real command/log artifacts.

2. **Use strict flags at confidence boundaries.**
   Add strict fields to relevant plan dataclasses instead of making every
   helper call immediately breaking. Strict mode is required by docs and tests
   for parent/full confidence. Non-strict mode can still summarize legacy
   evidence but must not be used for final closure.

3. **Derive pass status from proof artifact when strict mode is on.**
   Evidence rows may keep their historical `result_status` fields, but strict
   reviews reject a row without a current passing artifact. If both exist and
   conflict, the artifact wins and the mismatch is reported.

4. **Represent legacy path disposition as model-miss closure evidence.**
   Add small dataclasses for old-path dispositions: deleted, blocked,
   delegated to repaired path, same-contract repaired, out of scope, or
   unknown. Unknown or missing in strict mode blocks model-miss closure.

5. **Keep FlowPilot integration narrow.**
   FlowPilot known-friction matrices should start producing proof artifact refs
   around real validation outputs. They should not self-declare full evidence
   merely by writing `evidence_status: passed`.

## Risks / Trade-offs

- **Existing tests may assume default child proof is passed.**
  Mitigation: keep non-strict compatibility where practical, but add strict
  tests that fail without artifacts and update defaults where risk is highest.

- **Proof artifact refs can themselves be fabricated by a caller.**
  Mitigation: include result path, exit code, fingerprints, timestamps, and
  producer route so project-specific adapters and DevelopmentProcessFlow can
  cross-check freshness; document that strict closure needs real artifacts.

- **This does not execute commands inside review helpers.**
  Mitigation: background command runners and project adapters remain the right
  producers. FlowGuard review helpers validate the evidence boundary.

- **Installed skills can drift from repository skills.**
  Mitigation: sync `.agents/skills` to `$CODEX_HOME/skills` after
  tests pass and verify import/version from the editable install.

## Migration Plan

1. Add the proof artifact module, exports, and tests.
2. Extend layered proof, risk ledger, defect-family, model-test, and
   development-process evidence dataclasses with optional proof refs.
3. Add strict-mode blockers for missing, stale, mismatched, or internal-only
   proof artifacts.
4. Add legacy-path disposition review for model-miss closure.
5. Update docs, templates, skills, OpenSpec tasks, changelog, and package
   version.
6. Install the editable package locally and sync repository skills into the
   installed Codex skill directory.
7. Run focused tests first, then broader model/package regressions in
   background where practical.
