---
name: flowguard-model-topology-hazard-review
description: Use when a locally green FlowGuard model needs topology-grounded future-use hazard review for broad claims, business paths, old/new disposition, side effects, terminals, loops, external boundaries, or parent/child compression.
---

# FlowGuard Model Topology Hazard Review

## Purpose
Infer actionable future-use hazards from the actual model topology and usage intent; keep unanchored AI concerns observation-only.

## Entrypoint Scope
Route id: `model_topology_hazard_review`; role: `public_owner`; native owner: `model_topology_hazard_review`. This standalone FlowGuard satellite skill owns topology-anchored risk routing, not generic brainstorming.

## Local Material Routing
Read `references/topology_hazard_protocol.md` for `TopologyDigest`, `UsageIntent`, business-path identity, anchors, dispositions, and completion rules.

## Entrypoint Acceptance Map
Accept a current topology digest, usage intent, and evidence boundary; promote only anchored hazards; block unresolved high-impact paths/loops/side effects; hand model, test, reduction, process, and risk work to typed owners.

## Use When
- Use before broad done/release/publish confidence when local green may hide duplicate/conflicting paths, broad terminals, repeatable side effects, compatibility paths, or closure/liveness hazards.

## Do Not Use When
- Do not use for generic risk lists, unmodeled systems, or as a replacement for maturation, alignment, Risk Evidence Ledger, or Architecture Reduction; return unclear topology to `flowguard`.

## Required Workflow
1. Record usage, scope, topology, business paths, evidence, and gaps. Portable temporal claims bind the digest to the exact `flowguard.portable_model.v1` fingerprint and executable obligations.
2. For each candidate, name the topology anchor, real-use failure, affected element, confidence effect, and disposition.
3. Resolve, scope with rationale, or issue typed owner-route handoffs and maintenance obligations.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Unanchored concerns cannot block confidence; anchored hazards need current evidence, owner route, or explicit scoped disposition.
- Important path conflicts, loop liveness, compatibility/history, and template harvest closure must remain visible before broad confidence.
- Portable liveness/fairness requires canonical checker evidence for the same graph; prose/metadata and stale or truncated reports cannot pass.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus anchored candidates and confidence effects.


<!--VTP:target adapter/catalog;native validation;stale/ambiguous=block;preview!=proof;harvest:VTP-->
