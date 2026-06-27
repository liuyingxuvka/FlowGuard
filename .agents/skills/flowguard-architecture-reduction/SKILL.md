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
   deletion; do not leave alternate routes unless explicitly required.
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
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-architecture-reduction and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
