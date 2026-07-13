---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, proposal, feature, bug, refactor, UI, test, prompt, skill, workflow, or process work in an existing modeled system to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground new work in current existing model boundaries before another route changes them.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `existing_model_preflight` (`public_owner`); it is a companion preflight, not the change owner.

## Local Material Routing
Read `references/existing_model_preflight_protocol.md` for lookup, light/full search, ownership, reuse, and proof.

## Entrypoint Acceptance Map
Accept boundary/root; query/search; choose reuse, extend, child, new, or none; block duplicate-boundary risk and select a downstream route.

## Use When
- Use before non-trivial proposals/implementation where commitments, fields, similar models, or mesh evidence may own the change.

## Do Not Use When
- Do not implement, split, or replace native validation; skip trivial/no-context work and return unclear scope to `model-first-function-flow`.

## Required Workflow
1. Classify the subject as `skill_runtime` or `ordinary_software`; query canonical commitments from task plus exact id/path/tool/workflow/error clues before path discovery; select one grounded primary plane or preserve ambiguity.
2. Search current models/specs/docs/surfaces/records; add exact owner models from primary hits and classify old evidence.
3. Extract block/state/field/effect/entrypoint/commitment/intent/path/mesh ownership.
4. Independently inventory every declared same-intent surface, not only caller candidates.
5. Record lookup/fingerprint, primary/related hits, reuse, unknown/scoped surfaces, duplicate/stale risks, and typed handoff.

## Hard Gates
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework. Full mode precedes proposal/implementation.
- Missing/stale search or ownership, duplicate owners, unresolved mesh proof, or omitted same-intent surfaces block full preflight; equivalent current semantics default to reuse.
- Shared words cannot promote a wrong-plane hit. Missing/stale lookup falls back explicitly; ambiguity blocks full-confidence selection.
- Former `skill_runtime` shapes are rejection evidence, not live routes. An `ordinary_software` compatibility surface needs an explicit historical-input requirement and bounded reader owner before it can be proposed or reused.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, hits, ownership, plane lookup, reuse, and duplicate risks.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot approve downstream work.
