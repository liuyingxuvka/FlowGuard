# test-mesh-target-split-derivation Specification

## Purpose
This capability defines FlowGuard's Test Mesh Target Split Derivation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: TestMesh target split derivation
TestMesh SHALL require a parent validation boundary to include target split
derivation evidence before a parent/child suite or script layout can support
green parent gate confidence.

#### Scenario: Complete test target derivation
- **WHEN** a parent test gate includes a FlowGuard validation-structure source
  model id, target child suite ids, covered partition item ids, and rationale
  for the validation split
- **THEN** TestMesh may continue to ownership, freshness, skipped-test,
  background, and release-scope review without a target-derivation blocker

#### Scenario: Missing test target derivation
- **WHEN** a parent test gate contains child suites or partition items but no
  target split derivation evidence
- **THEN** TestMesh reports a target-derivation blocker and does not return a
  green parent gate decision

### Requirement: TestMesh derivation matches child suites
TestMesh SHALL reject target split derivations that name target child suites not
registered in the TestMesh plan.

#### Scenario: Unknown target suite
- **WHEN** target split derivation evidence names a child suite id that is not
  registered in the plan's child suite evidence
- **THEN** TestMesh reports invalid target suite derivation

### Requirement: TestMesh derivation coverage
TestMesh SHALL reject target split derivations that do not cover the parent test
partition items being used for the parent gate decision.

#### Scenario: Incomplete test derivation coverage
- **WHEN** a target test split derivation omits one or more parent partition item
  ids from its coverage list
- **THEN** TestMesh reports incomplete target derivation coverage
