## Why

FlowGuard already contains many route-specific templates and several proven model/test branches, but a new project still has to rediscover those branches manually. The current risk-template library can search and harvest cards, yet it cannot safely select a branch by exact applicability, distinguish a local candidate from a promoted public seed, or require the target author to close a selected branch. This change makes the reusable knowledge explicit and keeps it lightweight: future projects receive only selected branch scaffolds, never another project's truth or private provenance.

## What Changes

- Add a route-scoped template-seed contract with four layers: route scaffold, reusable branch seed, operator guide, and FlowGuard self-model.
- Add public executable templates for ModelMesh, ContractExhaustion, and reverse implementation-surface closure; reuse the existing discovery, shard, merge, authoring, and audit implementations.
- Extend template selection so exact `TaskFacts` predicates are required; unknown or multiple matches block, and fuzzy search remains recommendation-only.
- Require every selected branch to be resolved as `modeled` or `not_applicable` with proof before a target can pass its runner.
- Add portable, privacy-neutral seed metadata with protected error classes, states/effects, positive and known-bad cases, false-friend cases, applicability predicates, and completion evidence.
- Keep local harvest candidates separate from packaged promoted seeds; predictive-KB recommendations and source-project paths never become runtime template authority.
- **BREAKING**: remove any implicit keyword-based template application or automatic inheritance of stale/local seed records; incompatible seed records require direct manual rewrite or retirement.

## Capabilities

### New Capabilities

- `route-scoped-template-seeds`: exact, portable branch-seed selection, promotion, and pending-branch closure.
- `public-model-mesh-template`: executable parent/child topology and reattachment template with positive and negative cases.
- `public-contract-exhaustion-template`: finite-dimension contract-exhaustion template with denominator and oracle gates.
- `public-reverse-surface-template`: implementation-to-model and model-to-implementation reverse closure authoring template.

### Modified Capabilities

- `project-layout-contract`: public templates use the current role-root layout and create optional roots only when an artifact is selected.
- `flowguard-validation-evidence-lifecycle`: selected template branches produce target-owned evidence and cannot substitute for target model/test/release receipts.

## Impact

- FlowGuard template factories, CLI dispatch, risk-template/harvest helpers, template adapters, and their tests.
- New OpenSpec capability specs and current public documentation; archive/history artifacts are not rewritten.
- No consumer project's `.flowguard` directory, external repository, Git history, CI, tag, or release is modified.
