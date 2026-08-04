## ADDED Requirements

### Requirement: Complete project test inventory has terminal dispositions
Every required project test node SHALL have exactly one terminal disposition: behavior coverage, cross-owner integration coverage, supporting evidence, duplicate evidence, scoped exclusion, or blocked. Parameterized and subtest cases SHALL retain stable case identity when their assertions differ materially.

#### Scenario: Required test node is unbound
- **WHEN** a full blueprint inventory contains a required test node with no owner, coverage edge, or typed disposition
- **THEN** TestMesh SHALL report the node and block declared-complete project-test closure

#### Scenario: Test node covers several owners
- **WHEN** one test is intentionally shared across model owners
- **THEN** TestMesh SHALL require exact assertion or native-member coverage edges for each owner
- **AND** file-level matching alone SHALL NOT prove coverage

