# flowguard-field-prompt-reduction Specification

## Purpose
This capability defines FlowGuard's Flowguard Field Prompt Reduction behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: AI-facing field prompts are grouped
FlowGuard field inventory and prompt guidance SHALL distinguish starter,
advanced, and internal field exposure so AI agents do not treat all discovered
fields as default authoring fields.

#### Scenario: Inventory exposes AI surface tier
- **WHEN** the field lifecycle inventory is regenerated
- **THEN** each row includes an AI surface tier suitable for starter,
  advanced, or internal routing decisions

#### Scenario: Tiering does not delete fields by itself
- **WHEN** a field is classified as advanced or internal
- **THEN** the inventory does not claim the field is removable without owner,
  reader, writer, lifecycle, and test-binding evidence

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

