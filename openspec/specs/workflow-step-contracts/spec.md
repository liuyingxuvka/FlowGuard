# workflow-step-contracts Specification

## Purpose
TBD - created by archiving change add-workflow-step-contracts. Update Purpose after archive.
## Requirements
### Requirement: Workflow step contracts
FlowGuard SHALL provide a public workflow step contract data model that declares a required workflow step's identity, completion labels, prerequisite receipts, produced receipts, invalidated receipts, claim labels that require the step, skip policy, and optional code/test binding metadata.

#### Scenario: Contract captures prerequisite and produced receipts
- **WHEN** a user declares a contract for step `write_coverage_matrix` that requires receipts `change_inventory` and `risk_catalog` and produces receipt `coverage_matrix`
- **THEN** the contract preserves those receipt relationships in a serializable public object

#### Scenario: Legacy workflows remain valid
- **WHEN** a check plan has no workflow step contracts
- **THEN** FlowGuard SHALL run existing workflow, invariant, scenario, progress, contract, and conformance checks without requiring step-contract metadata

### Requirement: Step contracts compile to executable checks
FlowGuard SHALL compile workflow step contracts into ordinary invariants or equivalent executable checks that reject traces where prerequisite receipts are missing, invalidated receipts are reused, required receipts are skipped before a claim, or a forbidden skip is treated as completion.

#### Scenario: Later step runs before prerequisite receipt
- **WHEN** a trace completes a step whose contract requires receipt `coverage_matrix` before any current step produced `coverage_matrix`
- **THEN** the compiled check SHALL fail with a finding that identifies the blocked step and missing receipt

#### Scenario: Claim happens before required receipt
- **WHEN** a trace reaches a label such as `done_claimed` and a contract marks receipt `full_regression` as required for that claim label
- **THEN** the compiled check SHALL fail unless `full_regression` is current at the claim point

#### Scenario: Receipt becomes stale after invalidation
- **WHEN** a step invalidates receipt `coverage_matrix` after that receipt was produced
- **THEN** any later step or claim requiring `coverage_matrix` SHALL fail until the receipt is produced again

### Requirement: Concrete trace review
FlowGuard SHALL provide a trace-level step contract review that returns a structured report containing status, findings, current receipts, skipped steps, stale receipts, and the first failing trace step when applicable.

#### Scenario: Good trace passes with receipts
- **WHEN** a trace produces every required receipt in order and makes a claim after all claim-required receipts are current
- **THEN** the review report SHALL be OK and include the final current receipt set

#### Scenario: Bad trace reports first failure
- **WHEN** a trace skips a required step and later makes a gated claim
- **THEN** the review report SHALL be not OK and identify the first failing claim or step

### Requirement: Runner integration
FlowGuardCheckPlan SHALL accept workflow step contracts and `run_model_first_checks(...)` SHALL include them in audit and Explorer validation while reporting a dedicated `workflow_step_contracts` section.

#### Scenario: Plan includes step contracts
- **WHEN** a check plan includes workflow step contracts
- **THEN** the runner SHALL run the compiled checks and include a section summarizing the number of contracts and whether step-contract evidence passed

#### Scenario: Step contract violation fails model check
- **WHEN** a model trace violates a step contract during runner exploration
- **THEN** the model check result SHALL expose the violation as an invariant failure rather than treating the workflow as green

### Requirement: Conformance metadata checks
FlowGuard SHALL provide conformance replay rules that compare expected step-contract metadata with observed production replay metadata for completed step ids, produced receipts, invalidated receipts, and skipped step ids.

#### Scenario: Production replay omits produced receipt
- **WHEN** the abstract trace step metadata says receipt `coverage_matrix` was produced but the replay observation omits that receipt
- **THEN** the conformance rule SHALL report a step-contract metadata mismatch

#### Scenario: No step metadata is present
- **WHEN** neither the expected trace step nor the replay observation declares step-contract metadata
- **THEN** the conformance rule SHALL not create a mismatch by itself

### Requirement: Helper projections
FlowGuard SHALL provide helper projections from workflow step contracts into DevelopmentProcessFlow validation requirements and Model-Test Alignment obligations.

#### Scenario: Process requirements are generated
- **WHEN** a workflow step contract produces receipt `full_regression` and marks it required for claim `done_claimed`
- **THEN** the DevelopmentProcessFlow projection SHALL produce a validation requirement that can gate the corresponding claim scope

#### Scenario: Model obligations are generated
- **WHEN** a workflow step contract defines a required step
- **THEN** the Model-Test Alignment projection SHALL produce a required model obligation with type `workflow_step`
