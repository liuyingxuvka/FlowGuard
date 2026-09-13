## Purpose

Make hierarchical model and test composition a real finite execution contract: bounded child cells, typed cross-child joins, progress, and native receipts must support the parent claim, while any missing component blocks only the affected closure.

## ADDED Requirements

### Requirement: Parent claims consume complete finite child evidence
Each hierarchical parent SHALL consume exact child case IDs, cell results, cross-child connection results, progress evidence, and oracle verdicts; structural declarations or aggregate markers alone SHALL NOT support execution verification.

#### Scenario: Complete five-level execution
- **WHEN** every declared leaf cell, sibling join, parent aggregation, and bounded progress trace has a current native receipt
- **THEN** the parent emits an execution-verified result whose denominator and fingerprints match the declared finite boundary

#### Scenario: A child cell or connection is missing
- **WHEN** one required cell, join, child receipt, oracle dimension, or progress artifact is absent, stale, or foreign
- **THEN** the affected parent and its ancestors are blocked while unrelated siblings remain independently reusable

### Requirement: Composition agrees with a bounded flat reference
For a bounded fixture with a declared shared property, the compositional execution SHALL agree with the flat reference on accepted and rejected systems; pairwise coverage SHALL NOT be promoted to an undeclared three-way property.

#### Scenario: Pairwise set misses a three-way defect
- **WHEN** a three-bit test set is pairwise complete but omits the `111` combination and the declared predicate requires all three bits
- **THEN** the global claim remains blocked or fails until the three-way property is declared and its missing cell is executed
