## ADDED Requirements

### Requirement: User-observed UI mismatch after green evidence is a model miss
Post-runtime Model Miss Review SHALL treat user-visible UI mismatch after a
green FlowGuard claim as a model miss. The review MUST record previous green
claim, observed UI failure, miss classification, why the previous model passed,
same-class UI controls or fields, and the tests or implementation evidence
needed to prevent recurrence.

#### Scenario: User opens UI and a wired button fails
- **WHEN** a user observes that an enabled UI button does not perform the
  claimed function after a prior green model or implementation claim
- **THEN** Model Miss Review classifies the issue as `evidence_overclaimed`,
  `boundary_missing`, `state_too_coarse`, `input_branch_missing`, or another
  supported miss type
- **AND** it requires same-class scan and same-class validation before broad
  closure

#### Scenario: Local patch cannot close UI miss
- **WHEN** a UI miss affects a class of buttons, fields, file pickers, table
  loaders, or visible state updates
- **THEN** repairing only the observed instance is insufficient for broad
  confidence unless same-class cases are explicitly scoped out with rationale

#### Scenario: Previous green reason is preserved
- **WHEN** a prior FlowGuard model or task was marked green before the UI miss
- **THEN** the miss review records which evidence passed, why it was too narrow,
  and which new model/test/validation row would have failed earlier
