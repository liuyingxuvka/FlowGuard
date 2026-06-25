---
name: flowguard-model-topology-hazard-review
description: Use when a locally green FlowGuard model still needs future-use hazard review from topology, usage intent, claim scope, old/new path disposition, business-path risk, side effects, terminals, loops, or parent/child compression.
---

# FlowGuard Model Topology Hazard Review

Standalone FlowGuard satellite skill for topology-grounded future-use hazards.
Return to `model-first-function-flow` when topology, intent, or ownership is unclear.

## First Read

- Route id: `model_topology_hazard_review`.
- Helpers: `infer_topology_digest()`, `infer_topology_hazard_plan()`,
  `review_topology_hazards()`, `UsageIntent`, `BusinessPathIdentity`,
  `TopologyHazardCandidate`.
- Reference: `references/topology_hazard_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current, or record why not.
- Do not create a fake mini-framework.
- Read topology before naming hazards; this is not a fixed risk checklist.
- Unanchored AI concerns are observations only.
- Hazard models need template-harvest closure.

## Inputs

- `TopologyDigest`: states, edges, side effects, terminals, old/new paths, business paths, external boundaries, parent/child compression, landmarks.
- `BusinessPathIdentity`: intent, trigger, terminal, writes, side effects,
  equivalent/exclusive/superseded paths, compatibility disposition, evidence.
- `UsageIntent`: use mode, final claim, history/compatibility, and goal.
- Current evidence: model pass, tests, replay, runner summary, skipped gaps.

## Review Rule

Every hard hazard names:

1. Topology anchor.
2. Future real-use failure mode.
3. Affected state, edge, side effect, terminal, legacy path, business path, or external boundary.
4. Disposition: model/test work, Risk Evidence Ledger, compatibility, scope, or blocker.

Generic warnings cannot block confidence without a topology anchor.

## Route Handoffs

- Coarse terminal, hidden post-success state, parent/child compression: `model_maturation_loop`.
- Model obligation or ordinary test gap: `model_test_alignment`.
- Broad final confidence or external proof gap: `risk_evidence_ledger`.
- Release/process/local-only evidence gap: `development_process_flow`.
- Old/new path or compatibility disposition: `architecture_reduction`, `risk_evidence_ledger`.
- Duplicate/conflicting/unproven business path: `architecture_reduction`,
  `model_similarity_consolidation`, `model_maturation_loop`,
  `model_test_alignment`, `risk_evidence_ledger`.

## Prompt

Use the protocol/template for full prompts. Output candidates with anchors,
rationale, future failure, disposition, route, confidence effect, and a status note.

## Non-Goals
- Do not replace Model Maturation, Model-Test Alignment, Risk Evidence Ledger, DevelopmentProcessFlow, or Architecture Reduction.
- Do not run LLM calls inside the Python package helper.
