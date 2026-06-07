---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, analysis, proposal, feature work, bug fix, refactor, UI flow change, test change, prompt change, skill change, or agent-workflow change in an existing modeled system so Codex grounds the route in current FlowGuard models before proposing new structure.
---

# FlowGuard Existing Model Preflight

Standalone FlowGuard satellite skill for grounding non-trivial work in current
model ownership before adding or changing a boundary. Use it for existing
prompt, skill, UI, test, process, feature, bug, or refactor surfaces. If the
change resembles another workflow, include Model Similarity Consolidation before
selecting reuse, extension, child model, or new boundary.

Return to `model-first-function-flow` when the FlowGuard route is unclear. Pair
this preflight with the downstream route that owns the actual work.

## First Read

- Route id: `existing_model_preflight`.
- Core helpers: `ExistingModelPreflight`, `ModelContextHit`,
  `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`,
  `existing_model_preflight_from_project()`,
  `review_existing_model_preflight()`.
- Model-angle companion: `ModelAngleDeliberation` and
  `review_model_angle_deliberations()` when the owner model may be too narrow.
- Similarity handoff: cite relation ids, maintenance group ids, change-impact
  ids, and impacted sibling model ids when A/B/C workflows may drift.
- Reference: `references/existing_model_preflight_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Prefer existing modeled responsibilities and field lifecycle ownership over
  parallel ownership.
- Keep stale, skipped, missing, and no-model-found evidence visible.
- Treat older model artifacts as upgrade-boundary inputs; run `project-upgrade`
  or `artifact-upgrade` before trusting old-shape evidence.

## Minimum Workflow

1. Search model records, docs, OpenSpec changes, and `.flowguard/`.
2. Extract FunctionBlock, state, side-effect, public-entrypoint, and field
   lifecycle owners.
3. Classify old-shape models as upgraded, blocked, or current before reuse.
4. Decide reuse, extend, add child model, new boundary, or no model found.
5. Record model-angle deliberation for missing-viewpoint risk; unresolved
   required angles block full preflight.
6. Route duplicate-boundary shrinkage to Architecture Reduction.

## Snapshot

Show existing model boundaries, field lifecycle owners/gaps, model-angle gaps,
reuse decision, duplicate-boundary risks, and downstream route.

## Non-Goals

- Do not implement production changes.
- Do not split code, tests, or models directly.
- Do not replace route-specific validation evidence.
