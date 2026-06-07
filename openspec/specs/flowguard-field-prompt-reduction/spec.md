# flowguard-field-prompt-reduction Specification

## Purpose
TBD - created by archiving change reduce-flowguard-field-prompts. Update Purpose after archive.
## Requirements
### Requirement: AI-facing field prompts are grouped

FlowGuard skill references SHALL prefer grouped field families over long
form-like lists when the grouped fields preserve the same evidence boundary.

#### Scenario: Routine route reads see grouped fields

- **WHEN** an agent reads Model-Test Alignment, DevelopmentProcessFlow,
  TestMesh, ModelMesh, or adoption-log guidance for routine use
- **THEN** the guidance presents compact field groups instead of requiring a
  blank for every optional text field
- **AND** uncommon details are clearly marked as expandable only when applicable

### Requirement: Quality-critical evidence fields remain visible

FlowGuard field prompt reduction SHALL preserve identity, status, freshness,
required evidence, external boundary, skipped/not-run, release-scope, and
scoped-gap fields.

#### Scenario: Reduced prompts still block overclaims

- **WHEN** an agent uses the reduced field guidance to make a done, release, or
  confidence claim
- **THEN** stale, skipped, failed, timeout, not-run, running, or progress-only
  evidence remains visible
- **AND** boundary inputs, outputs, state, side effects, error paths, assertion
  scope, and required evidence ids are still available when relevant

### Requirement: Prompt field regression is tested

The repository SHALL include tests that reject reintroducing long hot-path
field prompt lists in the reduced route templates.

#### Scenario: Long field lists return

- **WHEN** a changed prompt template reintroduces large numbers of colon-ended
  blank field prompts
- **THEN** skill documentation tests fail
- **AND** the failure points to the route whose field prompt needs grouping

