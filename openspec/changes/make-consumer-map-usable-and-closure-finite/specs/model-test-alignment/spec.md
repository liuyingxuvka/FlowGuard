## MODIFIED Requirements

### Requirement: Alignment remains affected-only during ordinary work

Ordinary alignment SHALL load only the affected model, owner, behavior, test,
and oracle neighborhood selected by an explicit typed change manifest or
declared relation. Whole-target alignment SHALL require an explicit
qualification or release scope. A pointer, report, task checkbox, output
directory, or test-time drift observation SHALL not be treated as the
ordinary change manifest.

#### Scenario: One binding changes
- **WHEN** one model-code-test binding changes without changing unrelated owners
- **THEN** only that binding and its affected parent/child closure SHALL become
  stale
- **AND** unrelated current receipts SHALL remain eligible for exact reuse

#### Scenario: No semantic source delta exists
- **WHEN** an explicit change manifest proves that functional model/code/test
  inputs are unchanged
- **THEN** alignment reports `no_semantic_change` with no model owners selected
- **AND** it does not authorize all models or activate a new revision

#### Scenario: Test-time source drift occurs
- **WHEN** a functional input changes between the start and end of a validation
  producer
- **THEN** that producer's receipt is invalid for alignment
- **AND** the drift is reported separately from the planned change scope

#### Scenario: Pointer-only binding changes
- **WHEN** only authority generation, activation, reverse binding, report, or
  task status changes and the selected functional inputs remain identical
- **THEN** alignment performs a finite binding integrity check
- **AND** it does not rerun the selected leaf or widen the affected closure
