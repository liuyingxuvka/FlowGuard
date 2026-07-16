## ADDED Requirements

### Requirement: Canonical Portable Model Schema
The system SHALL accept exactly the current `flowguard.portable_model.v1` schema and SHALL represent finite states, inputs, outputs, transitions, initial and terminal states, invariants, temporal obligations, assumptions, guarantees, and declared conflicts without executable project code.

#### Scenario: Current finite model is accepted
- **WHEN** a model uses the current schema and all ids and references are complete and unique
- **THEN** structural validation passes and returns the canonical model identity

#### Scenario: Alternate schema is rejected
- **WHEN** an artifact uses an unknown, retired, aliased, or missing schema id
- **THEN** validation fails visibly without selecting another reader

### Requirement: Stable Canonical Identity
The system SHALL serialize portable models as deterministic UTF-8 canonical JSON and SHALL compute identity from the exact canonical bytes.

#### Scenario: Equivalent key order has one identity
- **WHEN** two input documents differ only in object key order or insignificant JSON whitespace
- **THEN** their parsed current models produce identical canonical bytes and SHA-256 identity

#### Scenario: Semantic transition change stales identity
- **WHEN** a state, transition, obligation, assumption, or guarantee changes
- **THEN** the canonical identity changes

### Requirement: Finite Relation Semantics
The system SHALL interpret transitions sharing a source state and input symbol as the complete finite set of possible `(output, next state)` results for that input/state pair.

#### Scenario: Nondeterministic result set is preserved
- **WHEN** two transitions share a source and input but have different output or target pairs
- **THEN** execution returns both branches with their transition identities

### Requirement: Fail-Closed Structural Validation
The system SHALL reject duplicate ids, dangling state or transition references, non-JSON values, invalid bounds, malformed obligations, unreachable declared terminals when required, and unknown fields.

#### Scenario: Dangling transition target is invalid
- **WHEN** a transition targets a state absent from the model state inventory
- **THEN** validation returns an invalid finding and no checker pass receipt

