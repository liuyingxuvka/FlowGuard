## Context

The current `ModelMaturationSignal`, `ModelMaturationPlan`, `ModelMaturationReport`, and `review_model_maturation_loop()` are the correct owner. Existing route skills already produce state, branch, invariant, mesh, code-boundary, and freshness signals. The design must strengthen that owner without duplicating Model-Miss Review, ModelMesh, or Model-Test Alignment.

## Goals / Non-Goals

**Goals:**

- Represent a bounded task-local model-deepening session as immutable iterations.
- Derive closure from an independent coverage universe and current native probes.
- Force model-edit and evidence-acquisition gaps to continue; expose exact external blockers.
- Preserve base/candidate fingerprints, counterexamples, predictions, and rollback evidence.

**Non-Goals:**

- No numeric understanding levels or AI self-assessment.
- No mutation of FlowGuard algorithms, thresholds, or core rules at runtime.
- No new generic DiagnosisGuard or shared learning service.

## Decisions

1. Keep `model_maturation_loop` as the sole owner. Satellites only emit typed signals.
2. Add `resolution_class` values `model_edit`, `evidence_acquisition`, `external_input_required`, and `scope_excluded`. These route work; they do not score understanding.
3. Add a session/iteration record in the same module. A review command only validates it; the AI or caller creates candidate artifacts and reruns native checks.
4. Treat `model_closed_for_task` as the only normal terminal success. `external_input_required`, `scope_excluded_with_reason`, `progress_stalled`, and `iteration_limit_reached` remain visible non-success terminals.
5. Keep `confidence` as claim-support metadata only; it is not renamed into an understanding field.
6. Use one strict current schema. A non-trivial plan is invalid unless it binds
   task purpose, a separately produced coverage universe, the exact required
   probe inventory, base/candidate identities, and current native receipts.
   Former payloads fail visibly; there is no legacy reader or fallback.
7. Treat caller-authored `resolved`, gap deletion, arbitrary gap-transition
   dictionaries, and prose self-assessment as non-authoritative. Resolution
   and progress are derived from exact current receipt bindings.
8. A decision that requires another candidate (`upgrade_required`) is
   non-terminal. A session validates task identity, coverage identity,
   iteration continuity, predecessor fingerprints, and oscillation before it
   consumes another iteration.
9. Skill satellites emit typed signal/probe/receipt packets only. The kernel
   maturation loop remains the sole closure owner, and SkillGuard consumes the
   target-owned terminal receipt opaquely.

## Risks / Trade-offs

- [Existing callers assume empty signals mean current] -> update tests and all callers so non-trivial plans require purpose, universe, and probes.
- [A loop can run forever] -> use an iteration limit only as a safety blocker,
  plus candidate/evidence/gap-lineage progress detection and oscillation review.
- [A candidate can weaken obligations] -> require unchanged or expanded obligation/probe coverage and rerun known-good/known-bad checks.
- [A caller can forge closure-shaped fields] -> bind every resolution to a
  current receipt for the exact task, coverage universe, probe, and candidate.
- [A later model snapshot can overclaim coverage] -> include the runtime, CLI,
  tests, prompts, and target contract in the affected FlowGuard authority and
  model-test-alignment boundary.

## Migration Plan

Implement current-schema replacement, update fixtures and prompts, refresh the
observed model authority and target-owned SkillGuard contract, run affected and
frozen final validation, then regenerate and install the FlowGuard skill
projection. Publish only a new immutable version/tag; do not add legacy readers,
dual emission, or move an older tag.
