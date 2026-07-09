---
name: flowguard-existing-model-preflight
description: Use before discussion, proposal, feature, bug, refactor, UI, test, prompt, skill, or workflow change in an existing modeled system.
---

# FlowGuard Existing Model Preflight

Standalone FlowGuard satellite skill for grounding work in current model ownership before changing a boundary. If it resembles another workflow, include Model Similarity Consolidation before reuse, extension, child model, or new boundary.

Return to `model-first-function-flow` when the route is unclear. Pair this preflight with the downstream route that owns the actual work.

## First Read

- Route id: `existing_model_preflight`.
- Helpers: `ExistingModelPreflight`, `ModelContextHit`, `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, `existing_model_preflight_from_project()`, `review_existing_model_preflight()`.
- Behavior companion: identify affected commitment ids and owner models before creating a new boundary.
- Model-angle companion: `ModelAngleDeliberation`, `review_model_angle_deliberations()`.
- Similarity handoff: cite relation ids, maintenance groups, change-impact ids, sibling model ids.
- Reference: `references/existing_model_preflight_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Prefer existing modeled responsibilities and field lifecycle ownership over parallel ownership.
- Prefer existing commitments; overlap or unregistered external behavior routes to BCL.
- For add/change/remove/model-miss, identify affected commitment ids before creating or deepening a model boundary.
- Model misses first map to the existing owner model; ledger backfill only when no existing commitment covers the behavior.
- Keep stale, skipped, missing, and no-model-found evidence visible.
- Treat older model artifacts as upgrade-boundary inputs before trusting old-shape evidence.

## Minimum Workflow

1. Search model records, docs, spec-tool records, and `.flowguard/`.
2. Extract FunctionBlock, state, side-effect, public-entrypoint, and field lifecycle owners.
3. Classify old-shape models as upgraded, blocked, or current before reuse.
4. Decide reuse, extend, add child model, new boundary, or no model found.
5. Record affected commitment ids, owner model, siblings, and downstream route.
6. For replacements/removals, record old owner and old-path disposition to BCL, FieldLifecycleMesh, PPA.
7. Record model-angle deliberation; unresolved required angles block full preflight.
8. Route duplicate-boundary shrinkage to Architecture Reduction.

## Snapshot

Show existing model boundaries, field owners/gaps, model-angle gaps, reuse decision, duplicate-boundary risks, downstream route.

## Non-Goals

- Do not implement production changes.
- Do not split code, tests, or models directly.
- Do not replace route-specific validation evidence.
