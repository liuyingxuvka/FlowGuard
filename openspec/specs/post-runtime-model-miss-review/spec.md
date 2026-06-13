# post-runtime-model-miss-review Specification

## Purpose
This capability defines FlowGuard's Post Runtime Model Miss Review behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Model misses use five practical categories
The model-first Skill SHALL classify post-runtime model misses using the five
daily categories `boundary_missing`, `state_too_coarse`,
`input_branch_missing`, `invariant_too_weak`, and `evidence_overclaimed`.
Other details MAY be recorded as free-form notes but MUST NOT be required as
formal daily categories.

#### Scenario: Agent classifies a model miss
- **WHEN** runtime, test, replay, or manual validation exposes a bug after a
  FlowGuard pass
- **THEN** the agent records one of the five practical miss categories before
  trusting the repair

#### Scenario: Rare detail does not expand the category list
- **WHEN** a model miss has additional detail that does not fit neatly into the
  five categories
- **THEN** the agent may record the detail in plain language without adding a
  new required category

### Requirement: In-scope misses add one generalized bad case
The model-first Skill SHALL require an in-scope model miss to be represented by
the observed issue and at least one same-class generalized bad case when
practical before the model is trusted for the repair.

#### Scenario: Same-class bad case is practical
- **WHEN** the missed issue belongs inside the modeled boundary and a simple
  same-class variant can be expressed
- **THEN** the agent adds or updates executable model evidence so that the
  same-class bad case fails for the intended reason

#### Scenario: Same-class bad case is not practical
- **WHEN** the missed issue is outside the modeled boundary or a same-class
  variant is not practical for the current change
- **THEN** the agent records the reason instead of adding a generalized case

### Requirement: Adoption notes stay lightweight
The model-first Skill SHALL keep post-runtime model-miss adoption notes compact
by recording the miss type and the generalized case, or the reason no
generalized case was added. It MUST NOT require a default evidence-level field,
hazard registry, upgrade reviewer, model mesh, or full coverage matrix for
ordinary post-runtime model misses.

#### Scenario: Agent records the model-miss outcome
- **WHEN** an agent finishes post-runtime model-miss review
- **THEN** the adoption note includes `Miss type` and `Generalized case` or an
  explicit reason that the generalized case was not added

### Requirement: Model-miss review can derive family sibling bad cases

Post-runtime model-miss review SHALL be able to use obligation-family declarations to derive same-class sibling bad cases from an observed family-member miss.

#### Scenario: Observed miss creates sibling obligations
- **WHEN** a model miss is assigned to an obligation family member
- **AND** the family has other required members sharing the same mechanism
- **THEN** FlowGuard can derive sibling same-class bad cases for those members before the repair is broadly closed.

#### Scenario: Observed-only closure remains scoped
- **WHEN** only the observed failure case has evidence
- **AND** sibling same-class bad cases have not been generated or scoped out with reasons
- **THEN** model-miss closure remains scoped rather than full family confidence.

### Requirement: Model-miss review scans analogous defect radius

Post-runtime model-miss review SHALL ask where the same failure shape may recur and record dispositions for mandatory same-family siblings before broad closure.

#### Scenario: Same-family sibling is mandatory scan radius
- **WHEN** a model miss belongs to an obligation family member
- **AND** another required member shares the failed mechanism
- **THEN** FlowGuard treats that sibling as a must-scan analogous defect candidate.

#### Scenario: Open analogous candidate blocks full closure
- **WHEN** a must-scan candidate is unreviewed, marked repair-now, or marked model-upgrade-needed
- **THEN** full model-miss closure remains blocked until the candidate is repaired, covered by current evidence, or explicitly moved to a separate scoped change.

#### Scenario: Related surfaces remain visible without endless expansion
- **WHEN** a related surface is outside the direct family but has the same abstract failure shape
- **THEN** FlowGuard may record it as should-scan or record-only
- **AND** a concrete separate-change or exclusion reason keeps the current claim scoped rather than silently broad.

### Requirement: Model-miss review checks field lifecycle gaps
Post-runtime model-miss review SHALL treat missing field modeling, stale field
projection, hidden field reader/writer behavior, or unknown old-field
disposition as possible root-cause and closure gaps.

#### Scenario: Bug root cause is an omitted field
- **WHEN** runtime, test, replay, log, or manual evidence shows a bug caused by
  an omitted field or unmodeled field value
- **THEN** Model-Miss Review MUST backpropagate the root cause into field
  lifecycle coverage, model obligation, owner code contract, observed test, and
  same-class test evidence

#### Scenario: Same-class field bug is required
- **WHEN** a bug belongs to a field-related failure class and a generalized
  same-class case is practical
- **THEN** repair closure MUST include a same-class field case or an explicit
  scoped-out reason

### Requirement: Model-Miss Review handles non-trivial bug repairs
The Model-Miss Review route SHALL be used for non-trivial bug repairs when a
real bug, regression, failing test, log, manual validation result, production
evidence, or user-reported failure suggests that an existing model, test, or
confidence claim may have missed a failure class.

#### Scenario: Bug repair enters existing model-miss route
- **WHEN** an agent is asked to repair a non-trivial bug in a modeled or
  model-eligible system
- **AND** the bug is backed by real failure evidence or a user-visible failure
  report
- **THEN** the agent uses the existing Model-Miss Review route rather than
  treating the work as implementation-only

#### Scenario: Tiny bug remains scoped
- **WHEN** a bug repair is a tiny typo, formatting-only issue, or has no
  behavior/state/process confidence impact
- **THEN** the agent may skip Model-Miss Review with a concrete scoped reason

### Requirement: Bug repairs backpropagate the missed condition
Model-Miss Review SHALL ask for false-negative backpropagation evidence for
bug repairs by reusing the existing Plan Intake shape: previous passing claim,
observed failure, supported cause, would-have-failed-if condition, and new
plan/model/repair evidence.

#### Scenario: Root-cause backpropagation is complete
- **WHEN** a bug repair has a previous green claim or confidence statement
- **THEN** the repair evidence names the prior claim, the observed failure, why
  the prior evidence missed it, and which condition would have failed before
  closure if the model or evidence had been strong enough

#### Scenario: Root cause is missing
- **WHEN** a bug repair cannot name a supported cause or a would-have-failed-if
  condition
- **THEN** broad closure remains scoped or blocked until the gap is resolved or
  explicitly out of scope

### Requirement: Bug repair stays in existing route ownership
Model-Miss Review SHALL hand off model-code-test binding, stale evidence,
compatibility classification, legacy path disposition, mesh reattachment, and
final confidence to the existing owning routes instead of defining a separate
bug-fix workflow.

#### Scenario: Handoffs use existing owners
- **WHEN** a bug repair affects code contracts, tests, old paths, child models,
  or final confidence
- **THEN** the Model-Miss Review notes cite Model-Test Alignment,
  DevelopmentProcessFlow, Architecture Reduction, LegacyPathDisposition,
  ModelMesh/TestMesh when relevant, and Risk Evidence Ledger / Closure
  Contract as the owning evidence routes

### Requirement: User-observed UI confusion is a model miss
Model Miss Review SHALL treat user-observed confusion after green UI evidence
as a UI model miss, even when controls exist and click-through evidence passes.

#### Scenario: User cannot understand the intended operation
- **WHEN** a user reports that visible controls, text, keyboard behavior,
  regions, dialogs, or path-selection options are confusing
- **AND** prior FlowGuard evidence was green or used for a completion claim
- **THEN** the miss review records a human-operability miss class, previous
  claim, affected task/control/region, same-class candidates, root cause, and
  required same-class evidence

### Requirement: Source-target UI drift is a model miss
Post-runtime Model Miss Review SHALL classify user-observed source page, region, task, interaction, or control-placement drift after green UI evidence as a source-target model miss rather than a local button-only defect.

#### Scenario: Control appears in wrong target task
- **WHEN** a user reports that a source-based UI control appears in the wrong page, region, or user task after FlowGuard evidence was green
- **THEN** Model Miss Review records the previous green model, the real source expectation, the observed target drift, affected same-class controls or tasks, and the missing source-target mapping evidence

#### Scenario: Target document was wrong
- **WHEN** the target model is internally consistent but conflicts with the source baseline or approved difference ledger
- **THEN** Model Miss Review backpropagates the miss to source-baseline modeling and same-class counterexamples

