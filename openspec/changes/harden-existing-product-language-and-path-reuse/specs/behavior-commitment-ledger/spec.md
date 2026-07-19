## ADDED Requirements

### Requirement: Each exact business intent has one active commitment
Behavior Commitment Ledger SHALL assign one stable exact
`business_intent_id` and exactly one active commitment to each in-scope
external behavior promise. Exact identity SHALL be determined from the actor,
trigger and preconditions, expected result and terminal, failure boundary, and
material externally relevant state writes and side effects. Different UI, API,
CLI, alias, adapter, wrapper, helper, or compatibility surfaces for that exact
intent SHALL map to the same commitment.

#### Scenario: Multiple surfaces expose one exact intent
- **WHEN** several declared surfaces have the same actor, trigger and preconditions, expected result and terminal, failure boundary, material state writes, and side effects
- **THEN** the ledger SHALL map every surface to one stable business-intent id and one active commitment id

#### Scenario: Duplicate active commitments cover one exact intent
- **WHEN** two active commitment rows claim the same exact business-intent identity
- **THEN** the ledger review SHALL report a duplicate exact-intent commitment blocker and SHALL NOT support broad confidence

#### Scenario: A genuinely different intent remains separate
- **WHEN** a candidate commitment has a material externally observable difference in actor, trigger or preconditions, expected result or terminal, failure boundary, state writes, side effects, or safety semantics
- **THEN** the ledger SHALL require the difference, owner, validation boundary, rationale, and current evidence before accepting a distinct business-intent id

### Requirement: Delegating surfaces do not create delegate commitments
An additional surface that only delegates to the selected primary path SHALL be
recorded through the existing source-surface mapping and PPA candidate or facade
disposition. Behavior Commitment Ledger SHALL NOT create a delegate commitment,
surface commitment, or compatibility commitment whose only promise is to invoke
the same exact business intent.

#### Scenario: Compatibility facade delegates to the primary path
- **WHEN** an API alias, UI control, CLI command, adapter, wrapper, or compatibility facade adds no independent validation, terminal, state write, side effect, or success decision and delegates to the selected primary path
- **THEN** the ledger SHALL map that surface to the existing commitment without creating another commitment row

#### Scenario: Surface owns material behavior
- **WHEN** a proposed surface performs independent business validation, terminal selection, material state writes, side effects, or success behavior
- **THEN** the ledger SHALL treat it as a duplicate-path or distinct-intent question for the existing BCL/PPA owners rather than legitimizing it through a delegate commitment

### Requirement: Path-sensitive commitment bindings are singular and green
Each path-sensitive commitment SHALL bind to exactly one singular
`primary_path_id` whose PPA decision is current and green for the same stable
business-intent id. A report id, risk-gate id, receipt id, or free-form evidence
reference without a green singular path binding SHALL NOT satisfy broad
commitment coverage.

#### Scenario: Current green singular binding passes
- **WHEN** a path-sensitive commitment carries one primary path id, matching exact business-intent identity, current green PPA decision, and current runtime and proof evidence
- **THEN** the ledger review SHALL accept the PPA binding for the declared commitment scope

#### Scenario: Retired plural path input is not a runtime route
- **WHEN** normal runtime input supplies retired `primary_path_ids` or
  `legacy_primary_path_ids`
- **THEN** the ledger loader SHALL reject the input instead of migrating,
  aliasing, or selecting a list element
- **AND** historical file migration SHALL remain owned by the exact bounded
  artifact upgrader

#### Scenario: Scoped or opaque PPA reference is insufficient
- **WHEN** a path-sensitive commitment carries a PPA reference but the decision is scoped, missing, stale, blocked, not current, or lacks the selected primary path and material proof
- **THEN** the ledger SHALL keep commitment coverage scoped or blocked instead of treating the reference as passed
