## Why

ContractExhaustionMesh currently generates canonical bad cases from declared
boundaries, but it does not require every in-scope model in a hierarchy to
produce a local Cartesian coverage receipt, nor does it force every generated
combination case to close through model, code, test, parent consumption, and
final risk evidence. This lets agents overclaim broad confidence from partial
matrix coverage, child-local green results, or same-class bug examples that
were not expanded into model-scoped combinations.

## What Changes

- Add model-scoped Cartesian coverage to ContractExhaustionMesh: every
  in-scope model can declare local axes, interaction groups, combination cases,
  coverage receipts, and optional shards.
- Require hierarchical ModelMesh to track all in-scope model coverage receipts
  and to block parent confidence when any child receipt is missing, stale, or
  not consumed by the parent.
- Require Model-Test Alignment and TestMesh to consume generated combination
  case ids so every required case has semantic model/code/test binding and
  current test evidence or an explicit shard result.
- Extend RiskEvidenceLedger with final gates for all-model Cartesian coverage,
  unclosed shards, missing model receipts, and child-local green evidence that
  has not been consumed by the parent.
- Upgrade model-miss and bug-family closure so observed combination bugs become
  interaction groups and contract-exhaustion combination cases instead of
  remaining abstract same-class notes.
- Update skills, docs, templates, and topology guidance so agents cannot choose
  a low-coverage path by default or treat partial coverage as full coverage.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `contract-exhaustion-mesh`: add model-scoped Cartesian axes, interaction
  groups, combination cases, coverage receipts, and shard-aware decisions.
- `hierarchical-model-mesh`: require all in-scope model coverage receipts and
  parent consumption of child receipts before parent or root confidence.
- `model-test-alignment`: require generated combination cases to bind model
  obligations, owner code contracts, and current external test evidence.
- `test-evidence-mesh`: require TestMesh ownership and current evidence for
  generated combination cases and shards when validation is large.
- `risk-evidence-ledger`: require final broad claims to consume all-model
  Cartesian coverage and reject missing model receipts, unclosed shards, or
  unconsumed child coverage.
- `model-miss-test-evidence-closure`: require combination-type model misses
  and recurring bug families to promote into interaction groups and generated
  combination cases.

## Impact

- Affected code: `flowguard/contract_exhaustion.py`, `flowguard/hierarchy.py`,
  `flowguard/model_test_alignment.py`, `flowguard/testmesh.py`,
  `flowguard/risk_evidence_ledger.py`, `flowguard/obligation_family.py`,
  `flowguard/recurring_model_miss.py`, and `flowguard/__init__.py`.
- Affected tests: contract exhaustion, model mesh, model-test alignment,
  TestMesh, risk ledger, obligation family, recurring model miss, API surface,
  and skill-doc tests.
- Affected docs/skills: ContractExhaustionMesh, ModelMesh, Model-Test
  Alignment, TestMesh, ModelMissReview, RiskEvidenceLedger,
  DevelopmentProcessFlow, API surface docs, productized helper docs, modeling
  protocol, and topology docs.
