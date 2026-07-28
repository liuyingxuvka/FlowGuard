## Context

FlowGuard already has the main route pieces for finite bad-case governance:
ContractExhaustionMesh generates canonical mutation cases, ModelMesh governs
parent/child evidence, Model-Test Alignment binds model obligations to code and
tests, TestMesh owns large validation hierarchies, ModelMissReview and
BugFamily gates preserve same-class repairs, and RiskEvidenceLedger owns broad
confidence. The missing architecture is a hard all-model coverage layer:
agents can currently run one local matrix or one child route and overstate that
as whole-model Cartesian coverage.

The upgrade must respect the existing route cleanup. ContractExhaustionMesh
remains the only canonical generated bad-case route. Bug-family and model-miss
routes supply family seeds and root-cause dimensions; they do not become
parallel case generators. Parent models consume child summaries and coverage
receipts instead of expanding every child internal case into a global state
space.

## Goals / Non-Goals

**Goals:**

- Make Cartesian coverage model-scoped: every in-scope model declares local
  axes and receives its own coverage receipt.
- Let parent models consume child coverage receipts and interface output
  classes without multiplying every child internal case together.
- Generate stable combination case ids for local model interactions and parent
  interface interactions.
- Require generated combination cases to project into Model-Test Alignment,
  TestMesh, ModelMesh, and RiskEvidenceLedger.
- Preserve bug-family and model-miss routes as seed/closure owners while using
  ContractExhaustionMesh for canonical generated cases.
- Make broad/full claims fail when any in-scope model lacks coverage, any
  required case lacks test evidence, any shard is unfinished, or any child
  receipt is not consumed by its parent.

**Non-Goals:**

- Do not build a global project-wide Cartesian product across every child
  model's internal state space.
- Do not add a new public FlowGuard skill or parallel helper route.
- Do not remove existing single-dimension mutation case generation.
- Do not make Model-Test Alignment or TestMesh decide model hierarchy; ModelMesh
  remains the parent/child owner.

## Decisions

### Decision: Add model-scoped coverage objects to ContractExhaustionMesh

`ContractAxis`, `ContractInteractionGroup`, `ContractCombinationCase`,
`ContractCoverageShard`, and `ModelContractCoverageReceipt` will be added to
`flowguard/contract_exhaustion.py`. A `ContractExhaustionPlan` can still accept
the existing `dimensions` and `seed_cases`, but full hierarchical confidence
requires model-scoped receipts that name `model_id`, `model_level`,
`parent_model_id`, local axes, generated cases, coverage status, and shard
status.

Alternative considered: make every route invent its own combination ids. That
would recreate the helper-control-plane problem and make evidence hard to join.

### Decision: Use local Cartesian coverage plus parent interface coverage

Leaf and child models generate local combinations from their own axes. Parent
models consume child receipt ids, exposed output classes, and exposed error
classes, then generate interface combinations over those summaries. The parent
does not expand every child internal case.

Alternative considered: one global Cartesian matrix. This would state-explode
and hide model ownership boundaries.

### Decision: Make ModelMesh the all-model receipt owner

ModelMesh will receive a list of required model ids and coverage receipts. It
will report missing, stale, scoped, blocked, duplicate, or unconsumed receipts.
Parent confidence requires every in-scope child receipt to be current and
consumed by the parent coverage receipt or parent interface plan.

Alternative considered: make RiskEvidenceLedger infer the model tree directly.
That would duplicate ModelMesh hierarchy knowledge.

### Decision: Tests consume generated combination ids

Model-Test Alignment consumes generated combination cases as obligations.
TestMesh consumes combination case ids and shard ids as required leaf evidence
when validation is large or split. RiskEvidenceLedger consumes the final route
evidence and blocks overclaims.

Alternative considered: count a coverage receipt as proof by itself. That
would let generated cases bypass real tests.

### Decision: Bug families become model-deepening inputs

Observed combination bugs add or update `interaction_group_id`,
`observed_combination_case_id`, `affected_model_ids`, and generated case ids on
the existing family/miss structures. The actual case expansion remains in
ContractExhaustionMesh.

Alternative considered: replace BugFamily with ContractExhaustionMesh. That
would lose recurrence, provenance, and historical holdout semantics.

## Risks / Trade-offs

- Large local matrices can be expensive -> use explicit shards and require
  unfinished shard visibility instead of silent downscoping.
- Receipts could become declaration-only artifacts -> require MTA/TestMesh and
  RiskEvidenceLedger proof evidence before broad confidence.
- Existing users may have old plans without model ids -> keep ordinary scoped
  `review_contract_exhaustion()` behavior, but block full hierarchical
  coverage claims when model-scoped receipts are absent.
- Parent interface summaries can be too coarse -> ModelMissReview can
  backpropagate discovered cross-model misses into child interaction groups and
  parent interface axes.

## Migration Plan

1. Add data classes and review helpers while preserving existing APIs.
2. Export the new classes and projection helpers through the existing public
   `contract_exhaustion_mesh` API.
3. Add ModelMesh receipt-consumption checks.
4. Add MTA/TestMesh/RiskLedger integration helpers and tests.
5. Update bug-family/model-miss records to carry interaction group references.
6. Update skills, docs, templates, and topology.
7. Run focused tests, OpenSpec strict validation, project audit, full pytest,
   source/shadow/install sync checks, and Git verification.
