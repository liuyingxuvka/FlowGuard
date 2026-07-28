---
name: flowguard-existing-model-preflight
description: Use before non-trivial existing-system work to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground work in current model boundaries before another route changes them.

## Entrypoint Scope
This standalone FlowGuard satellite skill is the companion public lookup owner, not the downstream change owner.

## Local Material Routing
Read `references/existing_model_preflight_protocol.md` for lookup, search, ownership, reuse, and proof.

## Entrypoint Acceptance Map
Accept boundary/root; choose reuse, extend, child, new, or none; block duplicate ownership and select a downstream route.

## Use When
- Use before non-trivial proposals/implementation where commitments, fields, similar models, or mesh evidence may own the change.

## Do Not Use When
- Do not implement, split, or replace native validation; skip trivial/no-context work and return unclear scope to `flowguard`.

## Required Workflow
1. Audit the observed authority, query canonical commitments from exact task clues, and select one primary plane or preserve ambiguity.
2. Search models/specs/docs/surfaces, bind owners, classify old evidence, then attach WorkContexts with exact identities and lanes.
3. Extract block/state/field/effect/entrypoint/commitment/intent/path/mesh ownership.
4. Independently inventory every declared same-intent surface, not only caller candidates.
5. Record lookup/fingerprint, primary/related hits, reuse, unknown/scoped surfaces, duplicate/stale risks, and typed handoff.
6. For composition, report references, changed roots, discovery identity, and gaps through `compose_existing_models`; do not duplicate portable-system schema.

## Hard Gates
- A model is current only when its exact instance is in the observed snapshot for the current revision; other discovery is `candidate_only`.
- Missing, invalid, stale, or ambiguous authority blocks full preflight. Target and experiment snapshots may inform comparison but cannot own current behavior or current evidence.
- Model-purpose gate: pre-build/change freeze task-specific failure(s)/boundary; bind candidate to native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Require the real FlowGuard check engine and AGENTS.md managed record; forbid fake mini-frameworks. Full mode precedes proposal/implementation.
- Missing/stale search or ownership, duplicate owners, unresolved mesh proof, or omitted same-intent surfaces block full preflight; equivalent current semantics default to reuse.
- Shared words cannot promote a wrong-plane hit. Missing/stale lookup falls back explicitly; ambiguity blocks full-confidence selection.
- WorkContext is read-only context, never runtime ownership or evidence. Unknown adapters, stale fingerprints, missing roles, wrong lanes, path escape, or provider authority block.
- Select the owner closure before reading model bodies; broad authority inventory must be explicit.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, hits, ownership, plane lookup, reuse, and duplicate risks.
