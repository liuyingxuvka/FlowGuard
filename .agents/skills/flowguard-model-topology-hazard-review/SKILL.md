---
name: flowguard-model-topology-hazard-review
description: Use when a FlowGuard model that appears locally green needs experienced-engineer future-use risk inference from model topology, usage intent, final claim scope, old/new path disposition, side effects, terminal states, loops, or parent/child compression before broad confidence.
---

# FlowGuard Model Topology Hazard Review

Standalone FlowGuard satellite skill for topology-grounded future-use hazard
review before broad confidence. Return to `model-first-function-flow` when the
topology digest, usage intent, or downstream route ownership is unclear.

## First Read

Route id: `model_topology_hazard_review`.
Core helpers: `infer_topology_digest()`, `infer_topology_hazard_plan()`,
`review_topology_hazards()`, `UsageIntent`, `TopologyHazardCandidate`.
Reference: `references/topology_hazard_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Read topology before naming hazards; this is not a fixed risk checklist.
- Unanchored AI concerns are observations only; anchored scoped hazards can become maintenance obligations.

## Inputs

- `TopologyDigest`: states, edges, side effects, terminals, old/new paths,
  external boundaries, parent/child compression, and landmarks.
- `UsageIntent`: use mode, final claim, history/compatibility, and goal.
- Current evidence: model pass, tests, replay, runner summary, or skipped gaps.

## Review Rule

Every hard hazard must answer:

1. Which topology anchor caused the concern?
2. How could that shape fail in future real use?
3. Which state, edge, side effect, terminal, legacy path, or external boundary is affected?
4. Should it become model/test work, Risk Evidence Ledger evidence,
   compatibility disposition, scoped confidence, or a blocker?

Unanchored AI concerns are observations only. Do not let a generic warning block
confidence until it is bound to a concrete topology anchor.

## Route Handoffs

- Coarse terminal, hidden post-success state, parent/child compression: `model_maturation_loop`.
- Model obligation or ordinary test gap: `model_test_alignment`.
- Broad final confidence or external proof gap: `risk_evidence_ledger`.
- Release/process/local-only evidence gap: `development_process_flow`.
- Old/new path or compatibility disposition: `architecture_reduction` and `risk_evidence_ledger`.

## Prompt

Use the protocol and prompt template when a full prompt is needed. Keep output
as candidates with anchors, rationale, future failure mode, disposition,
required route, and confidence effect.
## Non-Goals

- Do not replace Model Maturation, Model-Test Alignment, Risk Evidence Ledger,
  DevelopmentProcessFlow, or Architecture Reduction.
- Do not run LLM calls inside the Python package helper.
