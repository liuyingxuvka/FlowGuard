## Purpose

Give projects a finite, auditable ContractExhaustion scaffold so exhaustive
testing proves a declared denominator and oracle rather than merely replaying
observed examples.

## ADDED Requirements

### Requirement: Exhaustion template requires a finite denominator and oracle

The public template MUST require finite dimensions, a member universe for each
dimension, allowed and rejected combinations, repair/normalization rules, an
oracle, stable case IDs, exclusions with proof, shard owners, receipts, and
Model-Test Alignment/TestMesh/ModelMesh handoffs.

#### Scenario: Finite contract is complete

- **WHEN** every dimension has a finite universe and every case has a stable
  ID and oracle result
- **THEN** the target can build deterministic exhaustion shards

#### Scenario: Observed examples are supplied without a denominator

- **WHEN** the model contains only cases seen in prior runs
- **THEN** the template blocks with a missing-denominator finding

### Requirement: Exhaustion rejects unsafe or incomplete spaces

The template MUST reject missing oracle, unbounded Cartesian products, missing
members, duplicate case IDs, stale universes, hidden fallback reject cases,
and UI exceptions without a finite boundary.

#### Scenario: Duplicate case identity is present

- **WHEN** two shards claim the same stable case ID
- **THEN** the contract check blocks before executing the duplicate case

#### Scenario: Reject case is hidden by fallback

- **WHEN** a normalization or fallback silently removes a declared rejected
  combination
- **THEN** the contract check reports the protected reject-case finding
