## ADDED Requirements

### Requirement: Model-first summaries expose inheritable obligations
Model-first FlowGuard summaries SHALL expose anchored non-pass gaps as
maintenance obligations when those gaps require future owner-route work.

#### Scenario: Summary gap creates owner-route obligation
- **WHEN** `run_model_first_checks(...)` produces a state-closure,
  topology-hazard, conformance, scenario, contract, progress, skipped, or
  not-run gap that has a concrete model, input, state, code, test, or
  public-surface anchor
- **THEN** the summary MUST be able to expose a maintenance obligation for that
  gap
- **AND** the obligation MUST preserve the owner route needed to resolve it

#### Scenario: Clean pass has no open obligations
- **WHEN** all summary sections pass and no scoped or not-run confidence gap is
  present
- **THEN** the summary MUST NOT invent open maintenance obligations

