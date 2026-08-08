## ADDED Requirements

### Requirement: Path-quality identities publish atomically with model revisions
ModelRevisionSet SHALL include the compact path-quality summary, subject identity, and detailed-evidence fingerprint for every added or replaced model in the same candidate and compare-and-swap activation as model content, cumulative intent, topology, bindings, and owner evidence. The independently derived add-or-replace set SHALL be the minimum required path-quality denominator, not an exact ceiling on supplied rows. A candidate MAY additionally carry path-quality rows for unchanged members through its complete current-model denominator, but every extra row SHALL belong to that same candidate's current model set, share the candidate snapshot, and be exact-current, validated, and resolved. A foreign, retired, stale, cross-snapshot, unvalidated, or unresolved extra row SHALL block acceptance. FlowGuard SHALL NOT maintain a second current path-quality pointer or activate an incomplete mixture of old and new rows.

#### Scenario: One affected model lacks path-quality evidence
- **WHEN** a candidate revision set changes several models and one affected model lacks a current required result
- **THEN** the whole candidate remains unaccepted without moving current authority

#### Scenario: Activation wins compare-and-swap
- **WHEN** all affected model and path-quality identities are current and the expected head still matches
- **THEN** they activate atomically under one transition receipt

#### Scenario: Small increment carries complete current DNA
- **WHEN** an independently derived revision adds or replaces 5 models in a candidate whose complete current-model denominator contains 51 models
- **AND** the candidate carries exact-current path-quality rows for all 51 current models from the same candidate snapshot
- **THEN** the 5 changed models satisfy the minimum required denominator
- **AND** the 46 unchanged current rows remain valid candidate DNA rather than causing an exact-equality rejection

#### Scenario: Extra row is foreign or stale
- **WHEN** all added or replaced models have current path-quality rows
- **AND** one additional row names a model outside the candidate current-model denominator, belongs to another snapshot, or is stale, unvalidated, or unresolved
- **THEN** the candidate remains unaccepted
- **AND** changed-member coverage SHALL NOT license the invalid extra row
