# validation-failure-triage Specification

## Purpose
TBD - created by archiving change add-validation-failure-triage. Update Purpose after archive.
## Requirements
### Requirement: Development validation failures are triaged before continuation

FlowGuard DevelopmentProcessFlow SHALL require agents to classify validation
failures before continuing implementation, rerunning validation, or claiming
done.

#### Scenario: Thick failure routes to owner satellite

- **WHEN** validation fails or reports an oversized model, oversized test/check,
  stale evidence, or disconnected parent/child evidence
- **THEN** DevelopmentProcessFlow MUST classify the failure and route
  model-too-thick cases to ModelMesh, test-too-thick cases to TestMesh,
  model-test mismatch cases to Model-Test Alignment, and stale or disconnected
  parent/child evidence back to the owning parent evidence gate

#### Scenario: Ordinary code failure remains ordinary after triage

- **WHEN** validation fails and triage classifies the failure as an ordinary
  implementation defect without thick model, thick test, stale evidence, or
  parent/child evidence risk
- **THEN** the agent MAY continue with the ordinary fix path while keeping the
  classification visible in the development evidence

### Requirement: Satellite handoffs preserve parent evidence confidence

FlowGuard satellite skills SHALL treat DevelopmentProcessFlow failure-triage
handoffs as owning-route obligations and SHALL require parent consumption of
new child evidence before parent confidence is claimed.

#### Scenario: ModelMesh receives model-too-thick handoff

- **WHEN** DevelopmentProcessFlow classifies a validation failure as
  model-too-thick or oversized model evidence
- **THEN** ModelMesh MUST derive or update the child model split, run child
  checks before the parent review, and require the parent to consume current
  child evidence instead of continuing to rely on the thick model as direct
  parent evidence

#### Scenario: TestMesh receives test-too-thick handoff

- **WHEN** DevelopmentProcessFlow classifies a validation failure as
  test-too-thick, slow/layered validation, stale test evidence, skipped
  evidence, or release-only evidence hiding parent confidence
- **THEN** TestMesh MUST derive or update the child validation structure,
  record child evidence status, and require parent validation confidence to
  consume current child evidence

#### Scenario: Model-Test Alignment receives mismatch handoff

- **WHEN** DevelopmentProcessFlow classifies a validation failure as model
  obligations not matching code contracts or ordinary test evidence
- **THEN** Model-Test Alignment MUST compare obligations, optional code
  contracts, and test evidence before alignment is claimed
