## ADDED Requirements

### Requirement: Product signatures are exact and bounded
ContractExhaustion SHALL bind every generated product to model id, ordered axis
ids, axis fingerprints, expected cardinality, partition revision, product kind,
and shard plan. It SHALL reject foreign-model axes, split singleton groups used
as a full product, and truncated products presented as complete. Exceeding the
configured finite bound SHALL remain a blocking split/shard disposition. A
coverage universe that intentionally uses multiple model-local products SHALL
declare `allow_partitioned_product` and separately provide typed parent or
cross-child handoff evidence; that declaration SHALL NOT weaken local product,
receipt, or connection checks.

#### Scenario: Foreign axis is referenced
- **WHEN** an interaction group for model P references an axis owned by model X
- **THEN** generation SHALL fail closed with an axis-model mismatch

#### Scenario: Full product is split into singleton groups
- **WHEN** required axes A and B appear only in separate singleton groups
- **THEN** `require_full_product` SHALL remain incomplete because A×B was not
  generated

#### Scenario: Partitioned local products are explicitly declared
- **WHEN** a parent universe covers child-local A and B products separately and
  sets `allow_partitioned_product` with typed cross-child handoff evidence
- **THEN** the parent SHALL not require a monolithic A×B table, but each local
  product and the handoff evidence SHALL remain independently complete

### Requirement: Cross-child handoff results are an explicit execution gate
ContractExhaustion SHALL distinguish generated cross-child handoff obligations
from independently produced terminal results. A plan that sets
`require_composite_handoff_results` SHALL require exactly one current,
fingerprinted result covering every route in each generated handoff; plans
that have not yet migrated this execution evidence MAY remain scoped, but a
supplied result is always validated and may not name an unknown obligation.

#### Scenario: Required handoff result is missing
- **WHEN** a broad plan enables `require_composite_handoff_results` and a
  generated case crosses two child routes without a terminal result
- **THEN** the plan SHALL remain blocked with an explicit missing-result
  finding

#### Scenario: Handoff result covers every route
- **WHEN** one current result is bound to the exact generated obligation and
  names every required route
- **THEN** that cross-child execution gate SHALL close without a missing,
  incomplete, or route-omission finding

### Requirement: Strict parent coverage resolves native child evidence
ContractExhaustion SHALL keep model-coverage receipts separate from execution
evidence. For strict full/release/whole-domain claims, every required child
coverage receipt SHALL map one-to-one to a canonical immutable
`EvidenceReceipt` loaded by exact receipt id from the declared store. An
independently derived verification context SHALL prove exact child
model/owner/parent/subject/scope/obligations/fingerprint/currentness and a
terminal exit-code-zero pass; id-only, aggregate, alias, ghost, duplicate,
foreign, stale, skipped, blocked, or parent-as-child evidence SHALL block.

#### Scenario: Strict parent resolves native child evidence
- **WHEN** a strict parent supplies exact native bindings, a canonical store,
  and independent verifier contexts for all required child coverage ids
- **THEN** every native receipt is loaded and checked before the parent can be
  accepted

#### Scenario: Strict parent has only an id set
- **WHEN** a strict parent records child coverage ids but omits native bindings
  or independent verifier contexts
- **THEN** the parent remains blocked with a visible native-evidence finding
