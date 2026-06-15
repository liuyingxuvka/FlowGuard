## ADDED Requirements

### Requirement: Model-Test Alignment consumes ModelMesh-derived transition cells
Model-Test Alignment SHALL treat ModelMesh-derived transition coverage cells as
ordinary required transition obligations and apply the existing code-contract,
evidence freshness, required-kind, target-id, and assertion-scope rules.

#### Scenario: ModelMesh-derived transition lacks test evidence
- **WHEN** a ModelMesh-derived transition obligation is required
- **AND** no current passing test evidence covers the matching transition cell
- **THEN** Model-Test Alignment SHALL report missing test evidence

#### Scenario: Rejection retry evidence is incomplete
- **WHEN** a ModelMesh-derived retry/rejection transition requires failure,
  negative, and replay evidence
- **AND** the bound tests only cover the happy path
- **THEN** Model-Test Alignment SHALL report missing required test kinds

#### Scenario: Fake-agent packet evidence remains scoped
- **WHEN** test evidence for a ModelMesh-derived AI packet handoff is synthetic
  or fake-agent-only
- **THEN** Model-Test Alignment SHALL treat it as contract or control-flow
  evidence unless a real external-contract assertion scope is supplied
