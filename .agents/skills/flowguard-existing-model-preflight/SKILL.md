---
name: flowguard-existing-model-preflight
description: Use before non-trivial existing-system work to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

This is a standalone FlowGuard satellite skill for existing-model lookup; it
does not replace the downstream owner or the FlowGuard check engine.

## Purpose
FlowGuard satellite for existing-model boundaries, ownership, evidence, and duplicate risk.

## Entrypoint Scope
It owns lookup, not the downstream route.

## Local Material Routing
After admission, read `references/existing_model_preflight_protocol.md` for lookup and proof.

## Entrypoint Acceptance Map
Choose reuse, extend, child, new, or none; block duplicate ownership; select a downstream route.

## Use When
- Use before non-trivial work where existing commitments, fields, or models may own the change.

## Do Not Use When
- Do not replace native validation; skip trivial work; return unclear scope to `flowguard`.

## Required Workflow
1. Audit the observed head, accepted revision, effective intent, commitments, and behavior plane.
2. Search affected models/specs/docs; bind owners, evidence, WorkContexts, and same-intent surfaces.
3. Report exact path-quality fingerprints or typed gaps; reuse only with exact identities and topology.
4. Preserve unknown, contradictory, unmapped, or scoped facts; return lookup, reuse, and duplicate risk.
5. Blueprint/qualification consumes owner, disposition, provider/profile, and finding identities. The native model directory is the only DNA source; standalone export is retired.

## Hard Gates
- Only an exact observed instance through the accepted revision and complete `CurrentEffectiveIntentView` is authoritative; history and path matches are candidates.
- Model-purpose gate: freeze task-specific failure(s) and claim_boundary; bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid fake mini-frameworks or caller-authored currentness.
- Shared words never promote a wrong-plane hit; WorkContext is read-only. Missing or stale owner/provider/mesh/path-quality identity blocks the claim.
- Lightweight path quality triggers ModelMaturation, not contraction, deep review, or code-edit authority.
- Blueprint handoffs never copy native inventories; ArchitectureReduction needs current equivalence/facade or retirement proof.
- Preflight proves lookup/scope only; ModelMaturation decides understanding and DevelopmentProcessFlow admission.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, hits, ownership, lookup/reuse, path gaps, and duplicate risks. Blueprint adds depth/first gap and handoffs; native-directory audit keeps static and execution status separate.
