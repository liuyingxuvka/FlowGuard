---
name: flowguard-existing-model-preflight
description: Use before non-trivial existing-system work to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground work in current existing model boundaries and duplicate-boundary risk before proposal or change.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns companion lookup, not the downstream route.

## Local Material Routing
After admission, read `references/existing_model_preflight_protocol.md` for the full lookup, ownership, reuse, and proof contract.

## Entrypoint Acceptance Map
Accept a boundary/root; choose reuse, extend, child, new, or none; block duplicate ownership; select a downstream route.

## Use When
- Use before non-trivial proposals/implementation where commitments, fields, similar models, or mesh evidence may own the change.

## Do Not Use When
- Do not implement, split, or replace native validation; skip trivial/no-context work and return unclear scope to `flowguard`.

## Required Workflow
1. Audit observed authority and commitments; select one plane or preserve ambiguity.
2. Search models/specs/docs/surfaces, bind owners, classify evidence, attach WorkContexts, and inventory every same-intent surface.
3. Emit provenance-bound facts and preserve unknown, omitted, contradictory, unmapped, and scoped facts; report lookup, reuse, risks, and a maturation contribution without claiming sufficiency.
4. For explicit blueprint/export/qualification scope, consume the independent inventory fingerprint, required ids, terminal dispositions, and unresolved findings. Ordinary work stays affected-only.
5. Composition reports references, changed roots, discovery identity, and gaps through `compose_existing_models`.

## Hard Gates
- Only an exact current observed instance is authoritative; other discovery is `candidate_only`. Missing/stale/ambiguous authority, ownership, mesh, or same-intent surfaces block full preflight.
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework. Full mode precedes change.
- Shared words never promote a wrong-plane hit; WorkContext is read-only; broad authority inventory must be explicit.
- Blueprint handoff references, but never copies or completes, the independent implementation inventory.
- Blueprint layers/depth, explicit whole scope, affected-only default, no owner fallback, and separate user/sufficiency/admission axes follow the protocol.
- Route ArchitectureReduction only for a concrete current model/code candidate with observable behavior-preserving evidence.
- Preflight proves lookup/scope only; maturation decides understanding and DevelopmentProcessFlow decides admission. Greenfield is `not_triggered`.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, hits, ownership, lookup, reuse, and duplicate risks. Blueprint output adds depth/first gap, inventory fingerprint, unresolved ids, and handoffs.
