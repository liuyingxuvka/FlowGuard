---
name: flowguard-existing-model-preflight
description: Use before discussion, proposal, feature, bug, refactor, UI, test, prompt, skill, or workflow change in an existing modeled system.
---

# FlowGuard Existing Model Preflight

Standalone FlowGuard satellite skill for grounding work in current model
ownership before changing a boundary. If the change resembles another workflow,
include Model Similarity Consolidation before selecting reuse, extension, child model, or new boundary.

Return to `model-first-function-flow` when the FlowGuard route is unclear. Pair
this preflight with the downstream route that owns the actual work.

## First Read

- Route id: `existing_model_preflight`.
- Core helpers: `ExistingModelPreflight`, `ModelContextHit`,
  `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`,
  `existing_model_preflight_from_project()`,
  `review_existing_model_preflight()`.
- Behavior companion: identify affected commitment ids and owner models before creating a new boundary.
- Model-angle companion: `ModelAngleDeliberation` and
  `review_model_angle_deliberations()` when the owner model may be too narrow.
- Similarity handoff: cite relation ids, maintenance groups, change-impact ids, and sibling model ids when workflows may drift.
- Reference: `references/existing_model_preflight_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Prefer existing modeled responsibilities and field lifecycle ownership over
  parallel ownership.
- Prefer existing commitments; suspected overlap or unregistered external behavior routes to `flowguard-behavior-commitment-ledger`.
- Keep stale, skipped, missing, and no-model-found evidence visible.
- Treat older model artifacts as upgrade-boundary inputs; run `project-upgrade`
  or `artifact-upgrade` before trusting old-shape evidence.

## Minimum Workflow

1. Search model records, docs, OpenSpec changes, and `.flowguard/`.
2. Extract FunctionBlock, state, side-effect, public-entrypoint, and field
   lifecycle owners.
3. Classify old-shape models as upgraded, blocked, or current before reuse.
4. Decide reuse, extend, add child model, new boundary, or no model found.
5. Record affected commitment ids, owner model, and siblings; unresolved duplicates route to the ledger.
6. Record model-angle deliberation; unresolved required angles block full preflight.
7. Route duplicate-boundary shrinkage to Architecture Reduction.

## Snapshot

Show existing model boundaries, field lifecycle owners/gaps, model-angle gaps,
reuse decision, duplicate-boundary risks, and downstream route.
Status note: searched boundary, hits/gaps, reuse, duplicate risk, route, next step.

## Non-Goals

- Do not implement production changes.
- Do not split code, tests, or models directly.
- Do not replace route-specific validation evidence.
