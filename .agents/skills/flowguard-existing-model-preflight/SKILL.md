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

1. Search model records, docs, OpenSpec changes, and .flowguard/.
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
Status note: searched boundary, hits/gaps, reuse, duplicate risk, route, next step.

## Non-Goals

- Do not implement production changes.
- Do not split code, tests, or models directly.
- Do not replace route-specific validation evidence.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-existing-model-preflight skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-existing-model-preflight activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
