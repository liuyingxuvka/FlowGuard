## MODIFIED Requirements

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
