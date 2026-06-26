---
name: flowguard-architecture-reduction
description: Use when a FlowGuard model should drive behavior-preserving architecture simplification, including merging duplicate handlers/modules, collapsing adapters, removing dead branches, or producing a StructureMesh-ready contraction plan.
---

# FlowGuard Architecture Reduction

Standalone FlowGuard satellite skill for model-backed contraction. Use it when
code, prompt, skill, or workflow structure can shrink without behavior drift.

Return to `model-first-function-flow` when the model is unclear. Hand concrete
public-entrypoint refactors to Code Structure Recommendation, StructureMesh, and
DevelopmentProcessFlow.

## First Read

- Route id: `architecture_reduction`.
- Contract first: entrypoints, outputs, state, side effects, gates, rationale.
- Core helpers: `ObservableArchitectureContract`,
  `ArchitectureReductionCandidate`, `review_architecture_reduction()`.
- Classify contraction candidates with proof status and required next route.
- Similarity handoff: cite relation/code obligation ids for duplicate
  boundaries or adapter-only differences.
- Reference: `references/architecture_reduction_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- Every candidate needs target action, proof status, next route, and scoped or
  risky obligations.
- Public entrypoints need StructureMesh or equivalent parity evidence.
- Compatibility-only branches, aliases, wrappers, old prompt fields, and
  replaced field aliases are removal candidates unless current contract,
  safety, facade, compatibility, archive, or negative-test evidence proves
  otherwise.
- Older same-class, analogous-bug, fallback prompt, or boundary-case generator
  paths that duplicate ContractExhaustionMesh are contraction candidates. Keep
  declaration owners and evidence consumers; remove parallel canonical
  generation paths.
- Reduction models need template-harvest closure.

## Minimum Workflow

1. Ground existing model ownership and duplicate-boundary risk.
2. Declare the observable contract.
3. Map FunctionBlock, state, side effect, and public entrypoint ownership.
4. Classify candidates as merge, collapse, remove, keep facade, or review.
5. Separate explicit safety/compatibility fields from removable surfaces.
6. Mark duplicate bad-case generators for ContractExhaustionMesh absorption or
   deletion; do not leave fallback routes unless explicitly required.
7. Separate ready, scoped, risky, and blocked candidates.

## Snapshot

Show boundary, observable contract, contraction candidates,
ContractExhaustionMesh absorption/deletion candidates, proof status, target
action, and required next route.
Status: contract, candidate, proof, risks, next route.

## Non-Goals

- Do not rewrite production code directly.
- Do not delete compatibility facades from property-only evidence.
- Do not hide skipped or stale conformance evidence.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-architecture-reduction skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-architecture-reduction activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
