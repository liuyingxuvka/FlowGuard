# FlowGuard Model Topology Hazard Review

## Purpose
Infer actionable future-use hazards from the actual model topology and usage intent; keep unanchored AI concerns observation-only.

## Entrypoint Scope
Route `model_topology_hazard_review` (`public_owner`); owns topology-anchored risk routing, not brainstorming.

## Local Material Routing
After selecting the subject, read `references/topology_hazard_protocol.md` for `TopologyDigest`, `UsageIntent`, business-path identity, anchors, dispositions, and completion rules.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

## Use When
- Use before broad done/release/publish confidence when local green may hide duplicate/conflicting paths, broad terminals, repeatable side effects, compatibility paths, or closure/liveness hazards.

## Do Not Use When
- Do not use for generic risk lists, unmodeled systems, or as a replacement for maturation, alignment, Risk Evidence Ledger, or Architecture Reduction; return unclear topology to `flowguard`.

## Required Workflow
1. Record usage, scope, topology, business paths, evidence, and gaps. Portable temporal claims bind the digest to the exact `flowguard.portable_model.v1` fingerprint and executable obligations.
2. Per candidate, name its topology anchor, real-use failure, affected element, confidence effect, and disposition.
3. Cross-model event/retry/resource/cache/atomicity/external-confirmation hazards may seed bounded interaction candidates, but must reference a BCL/preflight-resolved property owner or emit `owner_missing`; seeds are not executed findings.
4. Resolve, scope with rationale, or issue typed owner-route handoffs and maintenance obligations.

## Hard Gates

- Unanchored concerns cannot block confidence; anchored hazards need current evidence, owner route, or explicit scoped disposition.
- Keep path conflicts, loop liveness, and compatibility/history visible.
- Portable liveness/fairness requires canonical checker evidence for the same graph; prose/metadata and stale or truncated reports cannot pass.

## Output Requirements
- Return anchored candidates, confidence effects, `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`.
