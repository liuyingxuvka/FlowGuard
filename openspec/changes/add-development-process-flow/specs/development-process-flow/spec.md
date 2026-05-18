## ADDED Requirements

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
work but must be current for release claims.

#### Scenario: Routine scope defers release evidence
- **WHEN** a routine claim has all routine evidence current and release-required
  evidence pending
- **THEN** DevelopmentProcessFlow may allow routine confidence while reporting
  the release obligation as deferred

#### Scenario: Release scope requires release evidence
- **WHEN** a release claim lacks current release-required evidence
- **THEN** DevelopmentProcessFlow blocks release confidence

## MODIFIED Requirements

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
