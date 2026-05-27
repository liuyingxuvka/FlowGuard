## ADDED Requirements

### Requirement: Model-Test Alignment covers optional code external contracts
The `model_test_alignment` route SHALL compare FlowGuard model obligations,
optional code external contracts, and ordinary test evidence when code
contracts are in scope.

#### Scenario: Model-to-test alignment remains valid without code contracts
- **WHEN** a FlowGuard model has explicit obligations and no externally visible
  code contract is in scope for the current review
- **THEN** Model-Test Alignment compares `ModelObligation` rows directly with
  `TestEvidence` rows
- **AND** it does not require agents to invent code contract rows, split code,
  or invoke StructureMesh

#### Scenario: Code contracts are included when the external code surface is in scope
- **WHEN** the reviewed behavior depends on a public function, API, CLI,
  facade, adapter, persisted output, or other externally visible code surface
- **THEN** Model-Test Alignment includes optional `CodeContract` rows between
  `ModelObligation` rows and `TestEvidence` rows
- **AND** each owner code contract is bound to the model obligations it
  implements

#### Scenario: Code contracts can be required before rows exist
- **WHEN** the review declares that code external contracts are in scope but no
  code contract rows have been listed yet
- **THEN** the plan can require code contracts explicitly
- **AND** missing owner contracts block coverage instead of silently falling
  back to model-to-test-only confidence

### Requirement: Code contract rows expose externally visible behavior
When `CodeContract` rows are present, the review SHALL record enough behavior
surface to compare them with model obligations.

#### Scenario: Code contract fields are recorded
- **WHEN** an agent lists a code external contract
- **THEN** the row includes id, path, symbol, surface type, role, implemented
  model obligation ids, external inputs, external outputs, state reads, state
  writes, side effects, error paths, and required status

#### Scenario: Missing code contract owner blocks coverage
- **WHEN** a required model obligation has code contracts in scope but no owner
  contract implements that obligation
- **THEN** the review reports `missing_code_contract`
- **AND** the coverage claim remains blocked

#### Scenario: Code contract behavior mismatch stays visible
- **WHEN** a code contract owner is missing behavior required by the model
  obligation
- **THEN** the review reports `code_contract_missing_behavior`
- **AND** when the obligation requires an exact external contract and the code
  contract exposes extra behavior, the review reports
  `code_contract_extra_behavior`

#### Scenario: Duplicate code contract owners stay visible
- **WHEN** more than one owner code contract claims the same model obligation
  without explicit shared implementation intent
- **THEN** the review reports `duplicate_code_contract_owner`

### Requirement: Test evidence binds to code contracts when contracts are in scope
When code external contracts are included, ordinary test evidence SHALL bind to
both the relevant model obligations and the relevant code contract ids.

#### Scenario: Missing code-contract test evidence blocks coverage
- **WHEN** a required owner code contract has no current passing test evidence
  with external-contract or mixed assertion scope
- **THEN** the review reports `missing_code_contract_test_evidence`
- **AND** the coverage claim remains blocked

#### Scenario: Internal-path-only tests do not prove an external contract
- **WHEN** a test binds to a code contract but its assertion scope is
  `internal_path` or `unknown`
- **THEN** the review reports `test_checks_internal_path_only`

#### Scenario: Model-code-test binding mismatch stays visible
- **WHEN** test evidence names model obligations and code contracts whose
  implemented obligation sets do not overlap
- **THEN** the review reports `model_code_test_binding_mismatch`

#### Scenario: Unknown references stay visible
- **WHEN** code contracts reference unknown model obligations
- **THEN** the review reports `unknown_model_obligation_reference`
- **AND** when tests reference unknown code contracts, the review reports
  `unknown_code_contract_reference`

### Requirement: Model-Test Alignment remains independent from mesh routes
The route SHALL remain a direct alignment review and SHALL NOT become TestMesh,
StructureMesh, or ModelMesh.

#### Scenario: Large validation is routed separately
- **WHEN** the problem is large, slow, layered, stale-prone, or release-only
  validation evidence
- **THEN** the agent uses TestMesh instead of expanding Model-Test Alignment
  into a test hierarchy

#### Scenario: Code partition work is routed separately
- **WHEN** the problem is splitting code, APIs, modules, scripts, facades, or
  ownership boundaries
- **THEN** the agent uses StructureMesh instead of treating code contract rows
  as a refactor plan

#### Scenario: Model partition work is routed separately
- **WHEN** the problem is parent/child model evidence, multiple local models,
  or oversized model partitioning
- **THEN** the agent uses ModelMesh instead of reading mesh reports from
  Model-Test Alignment
