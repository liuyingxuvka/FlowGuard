---
name: flowguard-existing-model-preflight
description: Use before non-trivial existing-system work to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground existing model boundaries, ownership, evidence, path-quality currentness, and duplicate-boundary risk.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns lookup, not the downstream route.

## Local Material Routing
After admission, read `references/existing_model_preflight_protocol.md` for the lookup, ownership, reuse, and proof contract.

## Entrypoint Acceptance Map
Choose reuse, extend, child, new, or none; block duplicate ownership; select the downstream route.

## Use When
- Use before non-trivial proposals/implementation where commitments, fields, similar models, or mesh evidence may own the change.

## Do Not Use When
- Do not implement or replace native validation; skip trivial work; return unclear scope to `flowguard`.

## Required Workflow
1. Audit observed head, accepted revision, complete effective intent, commitments, and one behavior plane; preserve ambiguity.
2. Search only affected models/specs/docs/surfaces; bind owners, evidence, WorkContexts, and same-intent surfaces.
3. Report each affected owner's exact current compact path-quality fingerprints or a typed gap. Reuse only when every identity and affected topology is exact; ModelMaturation owns judgment.
4. Preserve provenance and unknown, omitted, contradictory, unmapped, or scoped facts; return lookup, reuse, duplicate risk, and a non-sufficiency maturation contribution.
5. Whole blueprint/export/qualification also consumes the independent owner denominator, dispositions, provider/profile identities, and unresolved findings. Handoffs carry exact references, changed roots, discovery identity, and gaps.

## Hard Gates
- Only an exact observed instance reached through accepted revision and complete `CurrentEffectiveIntentView` is authoritative; history, delta, word, and path matches are candidates only.
- Model-purpose gate: freeze task-specific failure(s) and claim boundary; bind the candidate to native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework or caller-authored currentness.
- Shared words never promote a wrong-plane hit; WorkContext is read-only. Missing, stale, or ambiguous owner/provider/mesh/same-intent/path-quality identity blocks its claim.
- Lightweight path quality is a ModelMaturation trigger, not contraction, deep-review, or code-edit authority; preflight does not enumerate candidates or recompute costs.
- Blueprint handoffs never copy native inventories. ArchitectureReduction needs a current candidate plus equivalence/facade or complete retirement proof.
- Preflight proves lookup/scope only; ModelMaturation decides understanding and DevelopmentProcessFlow admission. Greenfield is `not_triggered`.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, hits, ownership, lookup/reuse, path-quality gaps, and duplicate risks. Blueprint output adds depth/first gap, inventory fingerprint, unresolved ids, and handoffs.
