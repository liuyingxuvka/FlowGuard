# post-runtime-model-miss-review Specification

## Purpose
TBD - created by archiving change simplify-model-miss-review. Update Purpose after archive.
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

