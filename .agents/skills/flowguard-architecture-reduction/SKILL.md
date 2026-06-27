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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-architecture-reduction plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-architecture-reduction and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
