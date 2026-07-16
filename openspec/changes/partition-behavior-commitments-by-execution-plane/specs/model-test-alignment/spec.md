## ADDED Requirements

### Requirement: Plane-aware obligations bind model, owner code, and tests
Required behavior-plane, typed-relation, lookup, preflight, similarity, migration, and Model Miss obligations SHALL each bind one owner public code contract and current tests covering the same contract.

#### Scenario: Lookup obligation has external contract evidence
- **WHEN** plane-first lookup is required for the change claim
- **THEN** Model-Test Alignment SHALL bind the lookup obligation to the public lookup function/CLI contract and current same-plane/wrong-plane tests

#### Scenario: Internal scorer test is insufficient
- **WHEN** evidence tests only an internal token scorer and does not exercise the public lookup report boundary
- **THEN** alignment SHALL report an external-contract coverage gap

### Requirement: Migration evidence covers source and disposition
Migration obligations SHALL bind dry-run/apply behavior, canonical output, unknown-custom-Python rejection, semantic parity, and old-authority retirement to the upgrader's public contract and current artifact evidence.

#### Scenario: New ledger loads but old authority remains
- **WHEN** tests prove canonical loading but do not prove retirement of the embedded inventory
- **THEN** alignment SHALL keep the migration closure target open

### Requirement: Model Miss evidence binds same-plane backfeed
Model Miss repair evidence SHALL prove existing same-plane commitment reuse, missing-commitment gap backfill, and multi-plane primary/related separation through the owner public code contract.

#### Scenario: Point miss test passes without same-class case
- **WHEN** only the observed port-bridge example is tested
- **THEN** alignment SHALL report missing same-class/ContractExhaustion evidence for the declared family claim

### Requirement: Stable target ids close wrong-plane counterexamples
Every concrete wrong-plane or unsafe-merge counterexample produced during implementation SHALL receive a stable target id and current known-bad replay or counterexample-regression evidence.

#### Scenario: Cross-plane false friend is repaired
- **WHEN** a prior similarity result merged product and agent models
- **THEN** current evidence SHALL replay the exact target id and prove the public relation now remains false-friend/manual-review
