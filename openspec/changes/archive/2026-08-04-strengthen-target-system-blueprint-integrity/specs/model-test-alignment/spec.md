## REMOVED Requirements

### Requirement: Path and symbol binding is insufficient for reconstruction closure
**Reason**: The same semantic boundary is owned directly by static blueprint closure; the old title carried a retired product-branch name.

**Migration**: Use source-independent semantic specifications and oracles as requirements of static blueprint closure.

## ADDED Requirements

### Requirement: Path and symbol binding is insufficient for blueprint closure
A blueprint-required implementation binding SHALL cite current source-independent semantic specifications and applicable oracles for its input/output behavior, state and effects, error behavior, and relevant order, retry, timeout, or decision rules. A path and symbol without those references SHALL remain traceability-only evidence.

#### Scenario: Function path exists without semantic specification
- **WHEN** a model obligation binds a current function path and symbol but lacks required semantic or oracle references
- **THEN** ordinary traceability may pass while static blueprint closure remains incomplete

#### Scenario: Hidden writer is discovered
- **WHEN** source discovery finds a state or effect writer not present in the bound semantic write inventory
- **THEN** alignment blocks the blueprint and identifies the writer

### Requirement: Blueprint coverage is exact per behavior and checker member
Each blueprint coverage row SHALL bind one behavior block, semantic rule, external owner contract, primary implementation surface, owner-declared good, boundary, or bad case, oracle, accepted dimension checker design, and an exact current test node or native-check member.

#### Scenario: Checker id exists without a real assertion target
- **WHEN** a checker has an id and fingerprint but no current source assertion, delegated assertion chain, or native-check member
- **THEN** its design status SHALL remain planned or incomplete
- **AND** it SHALL NOT satisfy static model-code-test closure

#### Scenario: Aggregate suite omits one behavior member
- **WHEN** a parent suite exits successfully but its covered-member set excludes one required behavior block
- **THEN** that block SHALL remain `not_run` or incomplete
- **AND** the parent exit SHALL NOT be copied into the missing row

### Requirement: Execution receipts retain exact owner and subject identity
Execution evidence SHALL bind the producer owner, request, model and implementation fingerprints, covered obligations and members, toolchain, environment, result, and terminal artifact. A receipt SHALL NOT be relabeled or copied to another owner or uncovered subject.

#### Scenario: One receipt is relabeled for two owners
- **WHEN** a passing receipt produced for owner A is copied with owner B in a consumer row
- **THEN** owner B SHALL be rejected for producer, subject, or covered-member mismatch

#### Scenario: Required test is skipped or collects zero members
- **WHEN** a required member is skipped, xfailed, not run, or the runner succeeds while collecting zero matching members
- **THEN** execution closure SHALL remain incomplete

### Requirement: Static design and current execution remain independent
Complete static checker design MAY exist without a current run, but a release or executed-evidence claim SHALL require exact current terminal receipts for every required owner and member.

#### Scenario: Complete design has no current execution
- **WHEN** every behavior row has a real test or native-check design but current receipts are absent
- **THEN** static design MAY be complete
- **AND** execution SHALL remain `not_run` without changing the static result
