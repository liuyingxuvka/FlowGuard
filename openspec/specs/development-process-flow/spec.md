# development-process-flow Specification

## Purpose
TBD - created during OpenSpec archive normalization so historical
DevelopmentProcessFlow deltas can be archived into a main spec.
## Requirements
### Requirement: model-first-function-flow routes development lifecycle review
The `model-first-function-flow` Skill SHALL include
`development_process_flow` as a sibling route for development lifecycle
ordering, artifact overwrite, validation freshness, minimum revalidation, and
V-style lifecycle confidence.

#### Scenario: Route is listed beside sibling routes
- **WHEN** the Skill route map is read
- **THEN** `development_process_flow` is listed beside `core_modeling`,
  `model_test_alignment`, `model_mesh_maintenance`, `test_mesh_maintenance`,
  and `structure_mesh_maintenance`

#### Scenario: Route does not supervise sibling routes
- **WHEN** DevelopmentProcessFlow references evidence produced by TestMesh,
  StructureMesh, ModelMesh, Model-Test Alignment, LongCheck, or Conformance
  Adoption
- **THEN** the Skill guidance says it may use the sibling evidence id and
  freshness metadata but MUST NOT inspect, replace, or supervise that sibling
  route's internal review

### Requirement: DevelopmentProcessFlow triggers for staged work with validation
FlowGuard SHALL present DevelopmentProcessFlow as the route for any
non-trivial staged development or modification task where step ordering,
touched artifacts, validation evidence, evidence freshness, peer writes, or
minimum revalidation affects whether the agent can safely continue or claim
done.

#### Scenario: Staged implementation trigger
- **WHEN** an agent is asked to complete a non-trivial task with staged actions
  such as plan, edit, test, fix, and verify
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow` during planning

#### Scenario: Not reserved for release readiness
- **WHEN** a task is not yet at release, archive, publish, or final readiness
  but has multiple meaningful development stages and validation
- **THEN** the DevelopmentProcessFlow guidance still treats the route as
  applicable

#### Scenario: Trivial work can skip
- **WHEN** the task is a single-step typo, formatting-only edit, or pure
  explanation with no meaningful validation or artifact freshness risk
- **THEN** the guidance permits skipping DevelopmentProcessFlow with a clear
  reason

### Requirement: DevelopmentProcessFlow remains one sibling route
FlowGuard SHALL keep DevelopmentProcessFlow as one sibling route and SHALL NOT
split the Codex skill into separate lightweight and heavyweight modes for this
trigger clarification.

#### Scenario: Single route wording
- **WHEN** the satellite skill and route documentation are read
- **THEN** they describe direct use of `flowguard-development-process-flow`
  rather than introducing separate named modes

#### Scenario: Sibling evidence boundary preserved
- **WHEN** DevelopmentProcessFlow references evidence from ModelMesh, TestMesh,
  StructureMesh, Model-Test Alignment, LongCheck, or Conformance Adoption
- **THEN** the guidance continues to say it may use sibling evidence ids and
  freshness metadata but MUST NOT inspect, replace, or supervise sibling route
  internals

### Requirement: Evidence freshness and proof artifacts
FlowGuard SHALL let DevelopmentProcessFlow consume proof artifact metadata as
the concrete evidence boundary for validation freshness when a staged done,
release, archive, publish, or full-confidence claim depends on current proof.

#### Scenario: Evidence result path is missing
- **WHEN** strict process evidence is required and validation evidence declares
  a pass but has no result path or proof artifact reference
- **THEN** DevelopmentProcessFlow SHALL report incomplete validation evidence

#### Scenario: Artifact versions changed after proof
- **WHEN** a proof artifact covers older artifact versions than the current
  model, code, test, adapter, or requirement artifact
- **THEN** DevelopmentProcessFlow SHALL mark the proof stale and recommend
  revalidation

### Requirement: Development artifacts are versioned
FlowGuard SHALL allow projects to declare development process artifacts for
requirements, designs, models, source code, tests, validation adapters,
documentation, release assets, and sibling route reports with explicit current
versions and dependency metadata.

#### Scenario: Complete artifact registry
- **WHEN** every process action and evidence record references registered
  artifacts
- **THEN** DevelopmentProcessFlow reports no unknown-artifact finding

#### Scenario: Unknown artifact reference
- **WHEN** a process action or evidence record references an artifact that is
  not registered
- **THEN** DevelopmentProcessFlow reports an unknown-artifact finding

### Requirement: Process actions record lifecycle reads and writes
FlowGuard SHALL allow projects to declare ordered development process actions
with read artifacts, written artifacts, invalidated artifacts, produced
evidence, required evidence, actor metadata, and decision scope.

#### Scenario: Ordered lifecycle action
- **WHEN** an action writes a registered artifact
- **THEN** DevelopmentProcessFlow records that the artifact version changed for
  later evidence freshness checks

#### Scenario: Out-of-order lifecycle action
- **WHEN** an action declares an `order_after` dependency on an action that has
  not already occurred
- **THEN** DevelopmentProcessFlow reports an out-of-order process finding

### Requirement: Evidence freshness follows covered versions
FlowGuard SHALL mark validation evidence stale when a later process action
changes an artifact version that the evidence covers, directly invalidates that
evidence, or changes a verifier artifact used to produce that evidence.

#### Scenario: Code changes after unit pass
- **WHEN** unit-test evidence covers `code.module_a` at version 4 and a later
  action changes `code.module_a` to version 5
- **THEN** DevelopmentProcessFlow reports the unit-test evidence as stale

#### Scenario: Test changes after test pass
- **WHEN** test evidence covers `tests.module_a` as a verifier artifact and a
  later action changes `tests.module_a`
- **THEN** DevelopmentProcessFlow reports the earlier test evidence as stale

### Requirement: Freshness propagation is explicit
FlowGuard SHALL allow freshness rules that propagate upstream artifact changes
to downstream artifacts or evidence requirements, and SHALL report ambiguous or
unknown propagation policy before trusting a completion claim.

#### Scenario: Requirement change invalidates downstream evidence
- **WHEN** a freshness rule states that requirement changes invalidate design,
  model, code, and validation evidence, and a requirement changes after those
  records were produced
- **THEN** DevelopmentProcessFlow marks the affected downstream evidence stale

#### Scenario: Ambiguous freshness policy
- **WHEN** a completion claim depends on an artifact relationship with no
  explicit propagation rule
- **THEN** DevelopmentProcessFlow reports an ambiguous-freshness finding

### Requirement: Claims require current validation evidence
FlowGuard SHALL require done, release, archive, and publish-readiness claims to
be supported by current passing evidence that satisfies the relevant validation
requirements for the requested scope.

#### Scenario: Done claim with current evidence
- **WHEN** all required routine validation requirements have current passing
  evidence for current artifact versions
- **THEN** DevelopmentProcessFlow allows the done claim

#### Scenario: Release claim with stale evidence
- **WHEN** a release claim relies on evidence made stale by later artifact
  writes
- **THEN** DevelopmentProcessFlow reports a release-claim-with-stale-evidence
  finding and blocks release confidence

### Requirement: Background completion and skipped validation remain visible
FlowGuard SHALL distinguish current validation evidence from failed, skipped,
hidden-skip, not-run, timeout, running, and background progress-only evidence.

#### Scenario: Background progress-only evidence
- **WHEN** validation evidence is produced by a background run with progress
  output but no final exit or result artifact
- **THEN** DevelopmentProcessFlow reports progress-only evidence and does not
  count it as current validation coverage

#### Scenario: Hidden skipped validation
- **WHEN** validation evidence reports success while skipped validation is not
  visible
- **THEN** DevelopmentProcessFlow reports hidden-skipped validation and does not
  treat the evidence as sufficient

### Requirement: V-style validation pairs are supported
FlowGuard SHALL allow projects to declare validation requirements that pair
development artifacts with required validation evidence, including V-style
requirement/design/model/code-to-test relationships.

#### Scenario: Missing V-style validation pair
- **WHEN** a lifecycle plan declares a requirement-to-acceptance-test pair but
  no current evidence satisfies that pair
- **THEN** DevelopmentProcessFlow reports a missing V-model validation-pair
  finding

### Requirement: Minimum revalidation recommendations are derived
FlowGuard SHALL provide a deterministic revalidation recommendation for stale,
missing, failed, timeout, hidden-skip, progress-only, or not-run evidence that
prevents a claim from being supported.

#### Scenario: Revalidation after code and verifier changes
- **WHEN** a code artifact and its test artifact both change after prior test
  evidence
- **THEN** DevelopmentProcessFlow recommends rerunning the validation
  requirements that cover the current code and verifier artifact versions

### Requirement: Routine and release lifecycle scopes are distinct
FlowGuard SHALL distinguish routine lifecycle confidence from release
confidence so release-required evidence can be deferred visibly during routine
work but must be current for release claims, including local install and
shadow-workspace verification when the release process touches those artifacts.

#### Scenario: Routine scope defers release evidence
- **WHEN** a routine claim has all routine evidence current and release-required
  evidence pending
- **THEN** DevelopmentProcessFlow may allow routine confidence while reporting
  the release obligation as deferred

#### Scenario: Release scope requires release evidence
- **WHEN** a release claim lacks current release-required evidence
- **THEN** DevelopmentProcessFlow blocks release confidence

#### Scenario: Local release sync evidence is current
- **WHEN** a release claim includes a refreshed editable install and local
  shadow workspace sync
- **THEN** DevelopmentProcessFlow SHALL require final install and shadow import
  evidence for the released version before release confidence is claimed

### Requirement: DevelopmentProcessFlow consumes workflow step contracts
FlowGuard SHALL allow DevelopmentProcessFlow planning to consume workflow step contracts by projecting required receipts and claim gates into validation requirements that participate in missing, stale, skipped, failed, and progress-only evidence review.

#### Scenario: Step contract creates validation requirement
- **WHEN** a workflow step contract declares receipt `full_regression` as required for claim label `done_claimed`
- **THEN** the projection SHALL create a validation requirement that identifies the contract id, receipt id, and claim scope

#### Scenario: Projected requirement remains ordinary process evidence
- **WHEN** projected validation requirements are passed into `review_development_process_flow(...)`
- **THEN** DevelopmentProcessFlow SHALL review them with the same current, stale, skipped, failed, hidden-skip, not-run, running, and progress-only evidence rules used for manually declared validation requirements

### Requirement: Project adoption upgrade participates in process freshness
DevelopmentProcessFlow SHALL treat project FlowGuard adoption and upgrade
records as versioned process artifacts when a staged done, release, archive, or
publish claim depends on current FlowGuard guidance.

#### Scenario: FlowGuard guidance changes after validation
- **WHEN** a claim depends on FlowGuard Skill guidance or project adoption rules
- **AND** the FlowGuard package, managed AGENTS block, or project manifest has
  changed after the validation evidence was produced
- **THEN** DevelopmentProcessFlow reports that the prior evidence must be
  revalidated or the claim must be scoped

#### Scenario: Adoption log alone is insufficient
- **WHEN** an adoption or upgrade log entry exists but the required model/test
  validation evidence is missing or stale
- **THEN** DevelopmentProcessFlow does not treat the log entry as sufficient
  completion evidence
