---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, analysis, proposal, feature work, bug fix, refactor, UI flow change, test change, prompt change, skill change, or agent-workflow change in an existing modeled system so Codex grounds the route in current FlowGuard models before proposing new structure.
---

# FlowGuard Existing Model Preflight

Standalone FlowGuard satellite skill for grounding work in current model
ownership before adding or changing a boundary. Use it before non-trivial work
in an existing modeled system, especially prompt, skill, UI, test, process,
feature, bug, or refactor changes.
If a requested change resembles another existing workflow, use Model
Similarity Consolidation as part of this preflight and record the maintenance
group, impacted siblings, and false-friend rationale before selecting reuse,
extension, child model, or new boundary.

Return to `model-first-function-flow` when the FlowGuard route is unclear. Pair
this preflight with the downstream route that owns the actual work.

## First Read

- Route id: `existing_model_preflight`.
- Core helpers: `ExistingModelPreflight`, `ModelContextHit`,
  `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`,
  `review_existing_model_preflight()`.
- Similarity handoff: cite relation ids, maintenance group ids, change-impact
  ids, and impacted sibling model ids when A/B/C workflows may drift.
- Reference: `references/existing_model_preflight_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Prefer existing modeled responsibilities over parallel ownership.
- Keep stale, skipped, missing, and no-model-found evidence visible.

## Minimum Workflow

1. Search model records, docs, OpenSpec changes, and `.flowguard/`.
2. Extract FunctionBlock, state, side-effect, and public-entrypoint owners.
3. Decide reuse, extend, add child model, new boundary, or no model found.
4. Route duplicate-boundary shrinkage to Architecture Reduction.

## Snapshot

Show existing model boundaries, reuse decision, duplicate-boundary risks, and
downstream route.

## Non-Goals

- Do not implement production changes.
- Do not split code, tests, or models directly.
- Do not replace route-specific validation evidence.
