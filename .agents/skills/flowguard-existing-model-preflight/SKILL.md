---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, proposal, feature, bug, refactor, UI, test, prompt, skill, workflow, or process work in an existing modeled system to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground new work in existing model, behavior, field, state, side-effect, and entrypoint ownership before another route changes the boundary.

## Entrypoint Scope
Route id: `existing_model_preflight`; role: `public_owner`; native owner: `existing_model_preflight`. This standalone FlowGuard satellite skill is a companion preflight, not the downstream change owner.

## Local Material Routing
Read `references/existing_model_preflight_protocol.md` for light/full search, ownership snapshots, reuse decisions, duplicate risks, and layered proof status.

## Entrypoint Acceptance Map
Accept a target change boundary and project root; search current models/sources; choose reuse, extend, child, new boundary, or no-model-found; block unsupported ownership; hand typed work to the actual satellite owner.

## Use When
- Use before proposals or implementation in an existing modeled system, especially where behavior commitments, fields, similar models, or parent/child evidence may already own the change.

## Do Not Use When
- Do not implement, split code/tests/models, or replace route-native validation; skip typo/format/read-only work with no model context and return unclear work to `model-first-function-flow`.

## Required Workflow
1. Search model records, specs, docs, source surfaces, and repository-local FlowGuard records; classify old-shape evidence.
2. Extract existing FunctionBlock, state, field, side-effect, entrypoint, commitment, and parent/child ownership.
3. Record reuse decision, duplicate-boundary risks, affected siblings/commitments, stale gaps, and typed downstream route.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Full mode is required before proposal/implementation/major change; light notes cannot prove readiness.
- Missing search, stale ownership, unresolved model angles, duplicate owners, or unreviewed layered-proof status blocks full preflight.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus model hits, ownership, reuse decision, and duplicate risks.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks preflight coverage and cannot approve the downstream change.
