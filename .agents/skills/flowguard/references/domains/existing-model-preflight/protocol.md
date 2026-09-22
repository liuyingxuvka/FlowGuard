# FlowGuard Existing Model Preflight

This is an on-demand FlowGuard domain reference for existing-model lookup; it
does not replace the downstream owner or the FlowGuard check engine.

## Purpose
On-demand FlowGuard domain reference for existing-model boundaries, ownership, evidence, and duplicate risk.

## Entrypoint Scope
This domain reference owns lookup, not the
downstream route.

## Local Material Routing
After selecting the subject, read `references/existing_model_preflight_protocol.md` for
compact authority-first lookup and proof. Conditional change details are
named by that protocol only for implementation/model, whole-target, or
composition/path-quality triggers.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

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

- Shared words never promote a wrong-plane hit; WorkContext is read-only. Missing or stale owner/provider/mesh/path-quality identity blocks the claim.
- Lightweight path quality triggers ModelMaturation, not contraction, deep review, or code-edit authority.
- Preflight proves lookup/scope only; ModelMaturation decides understanding and DevelopmentProcessFlow admission.

## Output Requirements
- Return hits, ownership, lookup/reuse, path gaps, and duplicate risks. Blueprint adds depth/first gap and handoffs; native-directory audit keeps static and execution status separate.
