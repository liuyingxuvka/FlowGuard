## Context

The repository-wide field audit found 357 dataclasses and 3331 dataclass
fields. The highest-burden surfaces are not the core behavior fields; they are
horizontal gate columns, duplicated evidence-id shapes, report-only fields, and
historical compatibility fields exposed as normal route inputs.

Another active change, `add-field-evidence-route-binding`, is intentionally
minimal and reuses `FieldProjection.evidence_refs`. This cleanup should not
undo that work. It should remove other accumulated fields around the route.

## Goals / Non-Goals

**Goals:**

- Make the normal AI-authored schema smaller by deleting or merging fields that
  are derived, duplicate, report-only, or historical.
- Treat this as a breaking cleanup: do not keep legacy aliases, fallback
  constructor arguments, or old-field compatibility branches.
- Keep behavior-bearing fields such as external inputs/outputs, state
  reads/writes, side effects, error paths, field lifecycle, and field
  projections.
- Keep downstream proof authority with Model-Test Alignment, Runtime Path,
  AutoSplit, TestMesh, and Closure Contract instead of copying their fields into
  unrelated rows.

**Non-Goals:**

- Do not weaken broad confidence gates.
- Do not delete `FieldProjection.evidence_refs` route binding.
- Do not preserve old constructor shapes for previous FlowGuard versions.
- Do not turn this into a broad visual/UI redesign of FlowGuard routes.

## Decisions

1. **Risk rows use one gate list.**
   - Decision: introduce `RiskEvidenceGate(kind, evidence_id, required,
     current, confidence, scoped_reasons)` and replace all route-specific gate
     columns on `RiskEvidenceRow` with `gates`.
   - Rationale: every deleted gate cluster had the same meaning and review
     shape. A list lets one row mention only the gates it actually requires.
   - Alternative rejected: keep all old gate fields and hide them in docs. That
     would still leave the oversized API and AI-visible constructor surface.

2. **ProcessEvidence stops carrying AutoSplit metrics.**
   - Decision: remove state-count, test-count, duration, and auto-split fields
     from `ProcessEvidence`.
   - Rationale: auto-split already has `AutoSplitCandidate`; process evidence
     should record process proof, not duplicate split analysis.
   - Alternative rejected: keep metrics as optional process evidence fields.
     Optional fields still appear in templates, docs, and AI completions.

3. **Plan intake keeps one evidence-id shape.**
   - Decision: keep single mapping/source evidence ids in the normal mapping
     row and remove duplicate plural ids plus strict adapter-test flags from
     `EvidenceAdapterMapping`.
   - Rationale: mapping conformance checks can use explicit mapping rows; known
     bad fixture behavior belongs in tests, not normal plan input.
   - Alternative rejected: accept both singular and plural ids. That is exactly
     the kind of ambiguous field surface this cleanup is removing.

4. **Duplicate helper classes become one concept.**
   - Decision: merge same-field classes where they represent the same concept,
     such as residual and implementation blindspots.
   - Rationale: duplicated shape creates duplicate prompts, duplicate docs, and
     duplicate tests for no new behavior.

5. **Public API changes are intentionally breaking.**
   - Decision: update exports and tests to the new names and shapes rather than
     preserving removed names as aliases.
   - Rationale: the user explicitly requested direct deletion without old
     fallback preservation.

## Risks / Trade-offs

- **Risk: archived `.flowguard` models using removed fields fail under the new
  package.** Mitigation: run artifact/model upgrade or mark older artifacts as
  stale; latest-schema-first policy already permits deterministic cleanup.
- **Risk: broad confidence loses some gate visibility.** Mitigation: the
  generic `RiskEvidenceGate.kind` still records the gate kind, current status,
  confidence, and scoped reasons.
- **Risk: process evidence no longer auto-generates split findings.** Mitigation:
  use `AutoSplitCandidate` or `review_auto_mesh_splits()` for split review.
- **Risk: downstream docs/tests still reference removed fields.** Mitigation:
  run focused route tests, public template tests, API-surface tests, OpenSpec
  validation, and FlowGuard model checks before claiming completion.

## Migration Plan

1. Finish or avoid conflicting with `add-field-evidence-route-binding`.
2. Update OpenSpec and FlowGuard model artifacts for the breaking cleanup.
3. Patch the focused schemas and tests in small route-owned batches.
4. Run focused tests after each route batch.
5. Run broader unit regression and FlowGuard checks in background where useful.
6. Sync editable install and any shadow/local repository copies after tests are
   green.
