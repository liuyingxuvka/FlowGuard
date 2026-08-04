## ADDED Requirements

### Requirement: Deep blueprint rows bind model semantics code and tests exactly
For static blueprint qualification, Model-Test Alignment SHALL bind every in-scope model obligation through independent semantic evidence and one owner CodeContract to exact implementation surfaces and exact evidence producers. A producer SHALL be an independently re-discovered project test node with assertion-quality evidence or a bounded native model checker whose current project file is independently fingerprinted. Current execution receipts SHALL remain a separate evidence status and SHALL be required only for claims that say the current evidence executed successfully. Every identity and fingerprint consumed by either status SHALL remain explicit.

#### Scenario: One obligation has a complete current chain
- **WHEN** an obligation is linked to independent semantics, one current CodeContract, all implementing surfaces, exact current test nodes, and meaningful assertions
- **THEN** the row MAY report the static model-semantic-code-test binding complete
- **AND** the row exposes the consumed identities and fingerprints
- **AND** execution remains `not_run` until a separate current receipt exists

#### Scenario: A helper is found outside the declared binding
- **WHEN** independent implementation discovery finds a behavior-bearing helper consumed by an obligation but the alignment row omits it
- **THEN** the row remains incomplete and identifies the orphan implementation surface
- **AND** a passing test for another surface cannot substitute for the missing binding

#### Scenario: Test source exists without an executable node
- **WHEN** a test file is inventoried but its executable test node or collection identity is missing
- **THEN** the test remains an unresolved inventory item
- **AND** it does not satisfy the obligation row

### Requirement: Candidate test design and current evidence remain separate
Alignment SHALL distinguish candidate oracle and planned-test design from executed evidence for the current observed implementation. A future obligation MAY carry a planned test or falsifier, but its test status SHALL remain `planned` or `not_run` until the exact candidate implementation is executed and evidenced.

#### Scenario: A future obligation has a planned falsifier
- **WHEN** a candidate target includes a test design and oracle but no candidate execution receipt
- **THEN** the alignment row reports pre-code test design present and executed evidence `not_run`
- **AND** it does not present the future obligation as current-green

#### Scenario: A broad test command passes
- **WHEN** a parent pytest command passes but an in-scope obligation lacks an exact child test node and binding row
- **THEN** the parent result remains aggregate execution evidence only
- **AND** the missing row remains visible and blocks static model-code-test closure

#### Scenario: One accepted future obligation has no test owner
- **WHEN** an accepted candidate obligation has neither a falsifier and planned test owner nor an explicit scoped disposition
- **THEN** Model-Test Alignment reports an unresolved evidence owner
- **AND** candidate readiness remains blocked
