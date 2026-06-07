## ADDED Requirements

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
